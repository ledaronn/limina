; pevrai.iss — Inno Setup 6 kurulum tarifi. Calistir: python packaging/build.py --kurulum
; (ya da: ISCC /DSurum=0.1.1 /DKok=<proje koku> packaging\pevrai.iss)
;
; Kullanici basina kurulum, YONETICI IZNI ISTEMEZ: %LOCALAPPDATA%\Programs\Pevrai.
; Kisisel veri (policy.toml, sohbetler, ayarlar) kurulum klasorunde DEGIL,
; %LOCALAPPDATA%\Pevrai ve ~/.vekil altinda; kaldirma onlara dokunmaz
; (yeniden kurunca ayarlar geri gelir). Silmek isteyen o klasorleri siler.

#ifndef Surum
  #define Surum "0.1.1"
#endif
#ifndef Kok
  #define Kok ".."
#endif

[Setup]
AppId={{DC6850D0-B387-4C2D-93DD-7ABBED9379EB}
AppName=Pevrai
AppVersion={#Surum}
AppVerName=Pevrai {#Surum}
AppPublisher=ledaronn
AppPublisherURL=https://github.com/ledaronn/pevrai
AppSupportURL=https://github.com/ledaronn/pevrai/issues
AppUpdatesURL=https://github.com/ledaronn/pevrai/releases
DefaultDirName={autopf}\Pevrai
DefaultGroupName=Pevrai
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile={#Kok}\LICENSE
SetupIconFile={#Kok}\pevrai\arayuz\pevrai.ico
UninstallDisplayIcon={app}\Pevrai.exe
UninstallDisplayName=Pevrai
OutputDir={#Kok}\dist
OutputBaseFilename=Pevrai-Setup-{#Surum}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Kok}\dist\Pevrai\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Pevrai"; Filename: "{app}\Pevrai.exe"
Name: "{autodesktop}\Pevrai"; Filename: "{app}\Pevrai.exe"; Tasks: desktopicon

; Keep the AppId stable for upgrades; remove only the previous product's launchers.
[InstallDelete]
Type: files; Name: "{app}\Limina.exe"
Type: files; Name: "{app}\limina-cli.exe"
Type: files; Name: "{autoprograms}\Limina.lnk"
Type: files; Name: "{autodesktop}\Limina.lnk"

[Run]
Filename: "{app}\Pevrai.exe"; Description: "{cm:LaunchProgram,Pevrai}"; Flags: nowait postinstall skipifsilent
