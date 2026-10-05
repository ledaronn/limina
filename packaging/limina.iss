; limina.iss — Inno Setup 6 kurulum tarifi. Calistir: python packaging/build.py --kurulum
; (ya da: ISCC /DSurum=0.1.0 /DKok=<proje koku> packaging\limina.iss)
;
; Kullanici basina kurulum, YONETICI IZNI ISTEMEZ: %LOCALAPPDATA%\Programs\Limina.
; Kisisel veri (policy.toml, sohbetler, ayarlar) kurulum klasorunde DEGIL,
; %LOCALAPPDATA%\Limina ve ~/.vekil altinda; kaldirma onlara dokunmaz
; (yeniden kurunca ayarlar geri gelir). Silmek isteyen o klasorleri siler.

#ifndef Surum
  #define Surum "0.1.0"
#endif
#ifndef Kok
  #define Kok ".."
#endif

[Setup]
AppId={{DC6850D0-B387-4C2D-93DD-7ABBED9379EB}
AppName=Limina
AppVersion={#Surum}
AppVerName=Limina {#Surum}
AppPublisher=ledaronn
AppPublisherURL=https://github.com/ledaronn/limina
AppSupportURL=https://github.com/ledaronn/limina/issues
AppUpdatesURL=https://github.com/ledaronn/limina/releases
DefaultDirName={autopf}\Limina
DefaultGroupName=Limina
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile={#Kok}\LICENSE
SetupIconFile={#Kok}\limina\arayuz\limina.ico
UninstallDisplayIcon={app}\Limina.exe
UninstallDisplayName=Limina
OutputDir={#Kok}\dist
OutputBaseFilename=Limina-Setup-{#Surum}
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
Source: "{#Kok}\dist\Limina\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Limina"; Filename: "{app}\Limina.exe"
Name: "{autodesktop}\Limina"; Filename: "{app}\Limina.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Limina.exe"; Description: "{cm:LaunchProgram,Limina}"; Flags: nowait postinstall skipifsilent
