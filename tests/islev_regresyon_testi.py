"""Gönderim, iptal, proje, not ve dönüştürücü hata yolları; kişisel veriye dokunmaz."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eklentiler_testi import Policy
from pevrai import journal, sohbet, taslak, projeler, ekip
from pevrai.eklentiler.registry import invoke
from pevrai.gui_kopru import Kopru
from pevrai.pencere import Api
from pevrai.olaylar import Oturum, Durduruldu
from pevrai.sonuc import hata
from pevrai.mcp_yazma import donustur
from pevrai.araclar.dosya import write_file


class Regression(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()  # 8.3 kisa ad (RUNNER~1) uzun ada cozulsun
        self.policy=Policy(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_send_rejection_keeps_attachments(self):
        api=Api.__new__(Api)
        api._ekler=['a.pdf']
        api._kopru=SimpleNamespace(calisiyor=lambda:False,oturum=Oturum(onay_saglayici=lambda _:False),
            gorev_baslat=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('busy')))
        self.assertFalse(api.gorev_baslat('test')['ok'])
        self.assertEqual(api._ekler,['a.pdf'])
        def accept(*a,**kw):
            self.assertIn('a.pdf',a[0]);api._ekler.append('new.pdf')
        api._kopru.gorev_baslat=accept
        self.assertTrue(api.gorev_baslat('test')['ok'])
        self.assertEqual(api._ekler,['new.pdf'])

    def test_retry_wait_stops_immediately(self):
        from pevrai.vekil_v0 import _yeniden_deneme_bekle, _model_cagir
        o=Oturum(onay_saglayici=lambda _:False)
        errors=[]
        def wait():
            try:_yeniden_deneme_bekle(o,25,'429')
            except Durduruldu:errors.append('stopped')
        th=threading.Thread(target=wait);th.start();o.durdur();th.join(timeout=1)
        self.assertFalse(th.is_alive());self.assertEqual(errors,['stopped'])
        provider=SimpleNamespace(uret=lambda *a: self.fail('stopped session sent request'))
        with self.assertRaises(Durduruldu):_model_cagir(provider,[],'fake','varsayilan',oturum=o)

    def test_failed_tool_is_string_with_failure_status(self):
        result=write_file(self.root/'missing'/'file.txt',{'content':'x'})
        self.assertIsInstance(result,str);self.assertFalse(result.basarili)

    def test_stop_after_rate_limit_does_not_send_second_request(self):
        from pevrai import vekil_v0 as v
        from pevrai.model.taban import OranSiniri
        o=Oturum(onay_saglayici=lambda _:False);calls=[]
        def generate(*a):
            calls.append(1);o.durdur();raise OranSiniri(429,'rate limit')
        fake=SimpleNamespace(politika=SimpleNamespace(gunluk_tavan={}),semalar=[])
        with patch.object(v,'B',fake),patch.object(v,'tavan_karari',return_value=None),patch.object(v.journal,'kota_artir'),patch.object(v.journal,'kota_sayaclari',return_value={}),patch.object(v,'sistem_talimati',return_value=''):
            with self.assertRaises(Durduruldu):v._model_cagir(SimpleNamespace(uret=generate),[],'fake','varsayilan',oturum=o)
        self.assertEqual(len(calls),1)

    def test_search_each_scope_and_v1_migration(self):
        def call(name,**args):return invoke(name,args,self.policy,root=self.root/'db')
        a=call('note_create',title='regression active')
        b=call('note_create',title='regression archived')
        c=call('note_create',title='regression deleted')
        call('note_archive',id=b['id'],expected_revision=1,archived=True)
        call('note_delete',id=c['id'],expected_revision=1)
        import sqlite3
        db=sqlite3.connect(self.root/'db'/'notes.sqlite3')
        db.execute('DELETE FROM note_search WHERE id<>?',(a['id'],))
        db.execute('PRAGMA user_version=1');db.commit();db.close()
        for scope,note in [('active',a),('archived',b),('deleted',c)]:
            result=call('note_search',query='regression',scope=scope)
            self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['id'],note['id'])

    def test_drafts_persist_without_note_revision(self):
        with patch.object(taslak,'YOL',self.root/'drafts.json'):
            note_id='a'*32;value={'title':'draft','body':'unsaved','baseRevision':2}
            taslak.yaz(note_id,value)
            self.assertEqual(taslak.oku()[note_id],value)
            taslak.yaz(note_id,None);self.assertEqual(taslak.oku(),{})
            with self.assertRaises(ValueError):taslak.yaz('../invalid',value)

    def test_chat_project_survives_restart_and_clear(self):
        with patch.object(sohbet,'KOK',self.root/'chats'):
            bridge=Kopru(kosucu=lambda *a,**kw:'ok')
            chat_id=bridge._aktif['id'];bridge.oturum.proje_baglami={'id':'a'*32,'name':'Example'}
            bridge._kaydet(bridge._aktif)
            self.assertNotEqual(bridge.yeni_sohbet(),chat_id)
            self.assertIsNone(bridge.oturum.proje_baglami)
            reopened=Kopru(kosucu=lambda *a,**kw:'ok')
            reopened.sohbet_ac(chat_id)
            self.assertEqual(reopened.oturum.proje_baglami['name'],'Example')
            reopened.oturum.proje_baglami=None;reopened._kaydet(reopened._aktif)
            cleared=Kopru(kosucu=lambda *a,**kw:'ok');cleared.sohbet_ac(chat_id)
            self.assertIsNone(cleared.oturum.proje_baglami)

    def test_project_payload_sent_to_model_without_ui_json(self):
        with patch.object(sohbet,'KOK',self.root/'chats'):
            received=[]
            def run(task,*a):received.append(task);return 'done'
            bridge=Kopru(kosucu=run)
            bridge._kos('message\n<untrusted_content>metadata</untrusted_content>',None,None,bridge._aktif,gosterim='message')
            events=bridge.olaylari_cek()
            started=next(e for e in events if e['tip']=='gorev_basladi')
            self.assertEqual(started['veri']['gorev'],'message')
            self.assertIn('metadata',received[0])

    def test_shared_projects_preserve_legacy_id(self):
        with patch.object(journal,'KOK',self.root/'data'),patch.object(ekip,'PROJELER',self.root/'legacy.json'):
            self.root.joinpath('legacy.json').write_text(json.dumps([{'kimlik':'old-id','ad':'Old','klasor':str(self.root),'aciklama':''}]))
            p=projeler.yaz(self.policy,'Shared',str(self.root),kimlik='old-id')
            self.assertEqual(p['kimlik'],'old-id');self.assertIn('workspace_id',p)
            canonical=invoke('workspace_get',{'id':p['workspace_id']},self.policy,root=journal.KOK/'eklentiler')
            self.assertEqual(canonical['name'],'Shared')
            new_root=self.root/'changed';new_root.mkdir()
            invoke('workspace_update',{'id':canonical['id'],'root':str(new_root),'expected_revision':canonical['revision']},self.policy,root=journal.KOK/'eklentiler')
            linked=projeler.liste(self.policy)
            self.assertEqual(len(linked),1);self.assertEqual(linked[0]['kimlik'],'old-id')
            self.assertEqual(Path(linked[0]['klasor']),new_root)
            projeler.sil(self.policy,'old-id');self.assertEqual(projeler.liste(self.policy),[])

    def test_workspace_delete_does_not_reimport_legacy(self):
        with patch.object(journal,'KOK',self.root/'data'),patch.object(ekip,'PROJELER',self.root/'legacy.json'):
            ekip.PROJELER.write_text(json.dumps([{'kimlik':'old-id','ad':'Old','klasor':str(self.root)}]))
            p=projeler.liste(self.policy)[0]
            w=invoke('workspace_get',{'id':p['workspace_id']},self.policy,root=journal.KOK/'eklentiler')
            invoke('workspace_delete',{'id':w['id'],'expected_revision':w['revision']},self.policy,root=journal.KOK/'eklentiler')
            self.assertEqual(projeler.liste(self.policy),[])

    def test_converter_overwrite_and_new_output_undo(self):
        with patch.object(journal,'KOK',self.root/'data'),patch.object(journal,'YEDEK',self.root/'data'/'backups'),patch.object(journal,'KAYIT',self.root/'data'/'journal.jsonl'):
            target=self.root/'out.pdf';target.write_bytes(b'original')
            def convert(args):
                Path(args['dst_dir'],'out.pdf').write_bytes(b'converted')
                Path(args['dst_dir'],'new.png').write_bytes(b'new')
                return 'ok'
            result=donustur(convert,{'dst_dir':str(self.root)},self.policy)
            self.assertTrue(result.basarili);self.assertEqual(target.read_bytes(),b'converted')
            journal.geri_al(str(target));self.assertEqual(target.read_bytes(),b'original')
            journal.geri_al(str(self.root/'new.png'));self.assertFalse((self.root/'new.png').exists())
            result=donustur(lambda args:hata('convert failed'),{'dst_dir':str(self.root)},self.policy)
            self.assertFalse(result.basarili);self.assertEqual(target.read_bytes(),b'original')
            with patch('pevrai.mcp_yazma.journal_yaz',side_effect=OSError('journal unavailable')):
                result=donustur(convert,{'dst_dir':str(self.root)},self.policy)
                self.assertFalse(result.basarili);self.assertEqual(target.read_bytes(),b'original')


if __name__=='__main__':unittest.main()
