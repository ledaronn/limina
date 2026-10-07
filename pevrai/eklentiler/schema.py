"""Provider-neutral JSON Schema vocabulary shared by tools and forms."""
def text(description="", max_length=500, required=False, **extra):
    return dict(type="string", description=description, maxLength=max_length, minLength=1 if required else 0, **extra)


def number(description="", minimum=0, maximum=100000, **extra):
    return dict(type="integer", description=description, minimum=minimum, maximum=maximum, **extra)


def choice(values, description=""):
    return dict(type="string", enum=values.split(), description=description)


def array(items, description="", limit=100):
    return dict(type="array", items=items, maxItems=limit, description=description)


def obj(fields, required=()):
    return dict(type="object", properties=fields, required=list(required), additionalProperties=False)


ID = text("Kayıt kimliği", 64, True)
REV = number("Okunan kaydın revision değeri; çakışmaları önler", 1)
TAGS = array(text("Etiket", 80, True), "Etiketler", 30)
DATE = text("Tarih", 10, True, format="date")
TIME = text("Saat dilimi içeren tarih/saat", 40, True, format="date-time")
REF = obj({"type": choice("course exam topic workspace task note"), "id": ID}, ("type", "id"))
REFS = array(REF, "Diğer eklentilere tür ve kimlik ile referanslar", 50)
PAGE = {"limit": number("Sayfa boyutu", 1, 100), "offset": number("Başlangıç", 0, 1000000)}


def tool(name, description, fields=None, required=(), risk="READ"):
    return dict(name=name, description=description, parameters=obj(fields or {}, required), risk=risk)


def crud(kind, label, fields, required, filters=None, delete=True):
    tools = [tool(kind + "_create", label + " oluştur.", fields, required, "WRITE"),
             tool(kind + "_get", label + " ayrıntısını oku.", {"id": ID, "include_deleted": {"type": "boolean"}}, ["id"]),
             tool(kind + "_list", label + " listesini oku.", {**PAGE, "include_deleted": {"type": "boolean"}, **(filters or {})}),
             tool(kind + "_update", label + " güncelle; önce güncel revision değerini oku.", {"id": ID, "expected_revision": REV, **fields}, ["id", "expected_revision"], "WRITE")]
    if delete:
        tools.append(tool(kind + "_delete", label + " kaydını silindi olarak işaretle; geçmiş korunur.", {"id": ID, "expected_revision": REV}, ["id", "expected_revision"], "DESTRUCTIVE"))
    return tools
