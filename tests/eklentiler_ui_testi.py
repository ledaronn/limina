"""Real pywebview asset server + browser + isolated plugin services. No model or external network."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eklentiler_testi import Policy
from pevrai.eklentiler.registry import catalog, invoke
from playwright.sync_api import sync_playwright, expect
from webview.http import start_server


def _wait_for_server(address: str, timeout: float = 10.0) -> None:
    """start_server() can return before its socket is accepting; navigating
    then gives ERR_CONNECTION_REFUSED and made this suite flaky under load."""
    import socket
    import time as _t
    from urllib.parse import urlparse
    parca = urlparse(address if "//" in address else "http://" + address)
    host, port = parca.hostname or "127.0.0.1", parca.port or 80
    son = _t.monotonic() + timeout
    while _t.monotonic() < son:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            _t.sleep(0.05)
    raise RuntimeError(f"asset server did not start listening on {host}:{port}")


def main():
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as pw:
        root = Path(temp)
        policy = Policy(root)
        opened_sources = []
        def api(name, args):
            try:
                if name == "okuma_kaynak_ac":
                    opened_sources.append(args[0])
                    return {"ok": True, "requested": True}
                if name == "eklenti_katalog":
                    return {"ok": True, "plugins": catalog(policy)}
                if name == "eklenti_cagir":
                    return {"ok": True, "result": invoke(args[0], args[1], policy, root=root / "db")}
                if name == "eklenti_ayarla":
                    if args[1]:
                        policy.kaldirilan.remove(args[0])
                    else:
                        policy.kaldirilan.append(args[0])
                    return {"ok": True}
                return {"ok": True, "olaylar": [], "sohbetler": [], "komutlar": [], "calisiyor": False}
            except Exception as exc:
                return {"ok": False, "hata": str(exc)}
        browser = pw.chromium.launch(channel="chrome", headless=True)
        # UTC: saat dilimi farki -0 olur (JS), Python tarafina float -0.0 gidiyordu (CI'da yakalandi)
        page = browser.new_page(viewport={"width": 1280, "height": 960}, timezone_id="UTC")
        errors = []
        def screenshot(suffix):
            if len(sys.argv) > 1:
                page.screenshot(path=str(Path(sys.argv[1]).with_suffix(suffix + ".png")))
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.expose_function("plugin_api", api)
        page.add_init_script("window.pywebview={api:new Proxy({}, {get:(_,name)=>(...args)=>window.plugin_api(name,args)})};")
        html = Path(__file__).resolve().parents[1] / "pevrai/arayuz/index.html"
        address, _, server = start_server([str(html)])
        assert Path(server.root_path).resolve() == html.parent.resolve()
        _wait_for_server(address)   # start_server returns before the socket accepts
        failed_assets = []
        page.on("response", lambda response: failed_assets.append(response.url) if response.status >= 400 and response.url.endswith(".js") else None)
        page.goto(address + "index.html")
        assert not failed_assets, f"Plugin scripts failed to load: {failed_assets}"
        assert page.evaluate("['today','connections','study','notes','workspace'].every(id => typeof window.PluginViews[id] === 'function')"), "Plugin views were not registered"
        page.evaluate("dilAyarla('tr')")
        page.locator("#ray-eklentiler").click()
        host = page.locator("#eklentiler-gorunum")
        expect(host.get_by_role("heading", name="Bir düşünceyle başla.")).to_be_visible()
        host.get_by_role("tab", name="Study & Focus", exact=True).click()
        host.get_by_role("tab", name="Dersler", exact=True).click()
        host.get_by_role("button", name="+ Ders", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Ad", exact=True).fill("Matematik")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Matematik", exact=True)).to_be_visible()
        host.get_by_role("tab", name="Sınavlar", exact=True).click()
        host.get_by_role("button", name="+ Sınav", exact=True).click()
        dialog.get_by_label("Ad", exact=True).fill("TYT deneme")
        dialog.get_by_label("Ders", exact=True).select_option(label="Matematik")
        dialog.get_by_label("Sınav tarihi ve saati", exact=False).fill("2026-10-12T09:00")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("TYT deneme", exact=True)).to_be_visible()
        exams = invoke("exam_list", {}, policy, root=root / "db")
        assert exams["items"][0]["name"] == "TYT deneme"
        host.get_by_role("tab", name="Odak", exact=True).click()
        host.get_by_role("button", name="Odak başlat", exact=True).click()
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_role("button", name="Duraklat", exact=True)).to_be_visible()
        host.get_by_role("button", name="Duraklat", exact=True).click()
        expect(host.get_by_role("button", name="Devam et", exact=True)).to_be_visible()
        host.get_by_role("button", name="Sohbete dön", exact=True).click()
        dock = page.locator("#ep-focus-dock")
        expect(dock).to_be_visible()
        dock.get_by_role("button", name="Devam et", exact=True).click()
        expect(dock.get_by_role("button", name="Duraklat", exact=True)).to_be_visible()
        for width in (390, 640, 1280):
            page.set_viewport_size({"width": width, "height": 960})
            dock_box, input_box = dock.bounding_box(), page.locator("#girdi").bounding_box()
            assert dock_box["y"] + dock_box["height"] <= input_box["y"], "Focus controls cover the chat input"
        screenshot(".chatfocus")
        dock.get_by_role("button", name="Odak", exact=True).click()
        screenshot(".focus")
        host.get_by_role("button", name="Bitir", exact=True).click()
        expect(dock).to_be_hidden()
        expect(host.get_by_role("button", name="Odak başlat", exact=True)).to_be_visible()
        host.get_by_role("tab", name="Smart Notes", exact=True).click()
        host.get_by_role("button", name="+ Yeni not", exact=True).click()
        dialog.get_by_label("Başlık", exact=True).fill("Türev")
        dialog.get_by_label("Not metni", exact=True).fill("<script>alert('xss')</script> Elektrik alanı")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Türev", exact=True)).to_be_visible()
        host.get_by_label("Not metni", exact=True).fill("Yeni türev notu")
        host.get_by_role("tab", name="Bugün", exact=True).click()
        host.get_by_role("tab", name="Smart Notes", exact=True).click()
        expect(host.get_by_label("Not metni", exact=True)).to_have_value("Yeni türev notu")
        host.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Yeni türev notu", exact=True)).to_be_visible()
        note = invoke("note_list", {}, policy, root=root / "db")["items"][0]
        host.get_by_label("Not metni", exact=True).fill("Kaydedilmemiş taslak")
        invoke("note_update", {"id": note["id"], "expected_revision": note["revision"], "body": "Asistanın yeni notu"}, policy, actor="ai", root=root / "db")
        host.get_by_role("tab", name="Bugün", exact=True).click()
        host.get_by_role("tab", name="Smart Notes", exact=True).click()
        expect(host.get_by_text("Asistan düzenledi", exact=True)).to_be_visible()
        expect(host.get_by_label("Not metni", exact=True)).to_have_value("Kaydedilmemiş taslak")
        host.get_by_role("button", name="Kaydet", exact=True).click()
        expect(page.get_by_text("Kayıt başka bir işlemde değişti. Yeniden okuyup güncelleyin.", exact=True)).to_be_visible()
        assert invoke("note_get", {"id": note["id"]}, policy, root=root / "db")["body"] == "Asistanın yeni notu"
        host.get_by_role("button", name="Değişiklikleri bırak", exact=True).click()
        expect(host.get_by_label("Not metni", exact=True)).to_have_value("Asistanın yeni notu")
        host.locator(".ep-editor-meta .ep-more > summary").click()
        host.get_by_role("button", name="Geçmiş / geri al", exact=True).click()
        expect(host.locator(".ep-compare")).to_contain_text("Asistanın yeni notu")
        expect(host.locator(".ep-compare")).to_contain_text("Yeni türev notu")
        screenshot(".history")
        host.get_by_label("Karşılaştırılacak sürüm", exact=True).select_option("2")
        host.get_by_role("button", name="Bu sürümü geri yükle", exact=True).click()
        expect(host.get_by_label("Not metni", exact=True)).to_have_value("Yeni türev notu")
        screenshot(".notes")
        host.get_by_role("tab", name="Workspace", exact=True).click()
        host.get_by_role("button", name="+ Yeni proje", exact=True).click()
        dialog.get_by_label("Ad", exact=True).fill("TYT Matematik")
        dialog.get_by_label("Proje klasörü", exact=True).fill(str(root))
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_role("heading", name="TYT Matematik", exact=True)).to_be_visible()
        host.get_by_role("button", name="+ Görev", exact=True).click()
        dialog.get_by_label("Başlık", exact=True).fill("Türev çalış")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Türev çalış", exact=True)).to_be_visible()
        host.get_by_label("Görev durumu: Türev çalış", exact=True).select_option("in_progress")
        expect(host.get_by_label("Görev durumu: Türev çalış", exact=True)).to_have_value("in_progress")
        host.get_by_role("button", name="Tamamla: Türev çalış", exact=True).click()
        expect(host.get_by_role("button", name="Yeniden aç: Türev çalış", exact=True)).to_be_visible()
        file = root / "ödev.txt"
        file.write_text("Soru 1", encoding="utf-8")
        host.get_by_role("tab", name="Dosyalar / çıktılar", exact=True).click()
        host.get_by_role("button", name="Dosya / çıktı bağla", exact=True).click()
        dialog.get_by_label("Dosya veya klasör yolu", exact=True).fill("ödev.txt")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Dosya · ödev.txt", exact=True)).to_be_visible()
        host.get_by_role("tab", name="Notlar", exact=True).click()
        host.get_by_role("button", name="Mevcut not bağla", exact=True).click()
        dialog.get_by_label("Not", exact=True).select_option(label="Türev")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(host.get_by_text("Yeni türev notu", exact=True)).to_be_visible()
        workspace = invoke("workspace_list", {}, policy, root=root / "db")["items"][0]
        host.get_by_role("button", name="Sohbette devam et", exact=True).click()
        expect(page.locator("#ep-chat-context")).to_contain_text("TYT Matematik")
        prompt = page.evaluate("LocalPlugins.chatPrompt('Devam edelim')")
        assert prompt.startswith('Devam edelim\n\nİlgili proje: ')
        assert '<untrusted_content source="workspace">' in prompt and workspace['id'] in prompt
        page.evaluate("yanitMesaji('Yakalanacak asistan yanıtı')")
        page.get_by_role("button", name="Nota kaydet", exact=True).click()
        expect(dialog.get_by_label("Not metni", exact=True)).to_have_value("Yakalanacak asistan yanıtı")
        dialog.get_by_label("Başlık", exact=True).fill("Sohbet notu")
        dialog.get_by_role("button", name="Kaydet", exact=True).click()
        expect(dialog).to_have_count(0)
        page.locator("#ep-chat-context").get_by_role("button", name="Projeyi aç", exact=True).click()
        host.get_by_role("tab", name="Bağlantılar", exact=True).click()
        host.get_by_label("Haritadaki düşünce", exact=True).select_option("workspace:" + workspace["id"])
        expect(host.locator(".ep-map svg line")).to_have_count(3)
        screenshot(".map")
        host.locator(".ep-map").get_by_role("button", name="Türev", exact=True).click()
        expect(host.locator(".ep-map-center")).to_have_text("Türev")
        host.get_by_role("button", name="Kaydı aç", exact=True).click()
        expect(host.get_by_label("Başlık", exact=True)).to_have_value("Türev")
        host.get_by_role("tab", name="Bugün", exact=True).click()
        expect(host.get_by_role("heading", name="Bir düşünceyle başla.")).to_be_visible()
        screenshot(".today")
        page.evaluate("dilAyarla('en')")
        expect(host.get_by_role("heading", name="Start with a thought.")).to_be_visible()
        page.evaluate("dilAyarla('tr')")
        for width in (390, 640, 960):
            page.set_viewport_size({"width": width, "height": 800})
            for route in ("Bugün", "Smart Notes", "Workspace", "Bağlantılar"):
                host.get_by_role("tab", name=route, exact=True).click()
                expect(host.locator(".ep-main > .ep-head h2")).to_have_text(route)
                assert host.evaluate("n => n.scrollWidth <= n.clientWidth + 1"), f"{route} overflows at {width}px"
                if width == 390 and route == "Bağlantılar":
                    host.get_by_label("Haritadaki düşünce", exact=True).select_option("workspace:" + workspace["id"])
                    screenshot(".map-narrow")
        page.set_viewport_size({"width": 1280, "height": 960})
        host.get_by_role("tab", name="Workspace", exact=True).click()
        if len(sys.argv) > 1:
            page.screenshot(path=sys.argv[1])
        page.set_viewport_size({"width": 640, "height": 480})
        assert host.evaluate("n => n.scrollWidth <= n.clientWidth + 1"), "Plugin panel overflows narrow screen"
        if len(sys.argv) > 1:
            page.screenshot(path=str(Path(sys.argv[1]).with_suffix(".narrow.png")))
        host.locator(".ep-main > .ep-head .ep-more > summary").click()
        host.get_by_role("button", name="Devre dışı bırak", exact=True).click()
        expect(host.get_by_role("button", name="Etkinleştir", exact=True)).to_be_visible()
        page.evaluate("delete window.PluginViews.notes")
        host.get_by_role("tab", name="Smart Notes", exact=True).click()
        expect(host.locator(".ep-error")).to_contain_text("arayüz dosyası yüklenemedi")
        host.get_by_role("tab", name="Study & Focus", exact=True).click()
        expect(host.get_by_role("tab", name="Odak", exact=True)).to_be_visible()
        host.get_by_role("button", name="Sohbete dön", exact=True).click()
        expect(page.locator("#girdi")).to_be_visible()
        source = "okuma://" + "a" * 24 + "/" + "b" * 32 + "/42"
        page.evaluate("text => yanitMesaji(text)", f"[Kaynak sayfa 42]({source}) [Dış bağlantı](https://example.com)")
        page.get_by_role("button", name="Kaynak sayfa 42", exact=True).click()
        assert opened_sources == [source]
        expect(page.get_by_role("button", name="Dış bağlantı", exact=True)).to_have_count(0)
        assert not errors, errors
        browser.close()
        print("PASS: pywebview assets, overview, real connections, focus dock, notes drafts/conflicts/history, workspace tasks/files/notes, chat capture/context, localization, responsive layout, disable and missing-view fallback")


if __name__ == "__main__":
    main()
