#define MyAppName "Mediiia публикатор"
#define MyAppVersion ReadIni(SourcePath + "\build.ini", "build", "version", "0.1.0")
#define MyAppExeName "MediiiaPublisher.exe"

[Setup]
AppId={{C18E96B7-7407-4DB7-9585-B59A3247D64A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=HSE Creative Hub
AppPublisherURL=https://github.com/ImStechen/mediiia-publisher
AppSupportURL=https://github.com/ImStechen/mediiia-publisher/issues
DefaultDirName={localappdata}\Programs\Mediiia Publisher
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=MediiiaPublisher-Setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked

[Files]
Source: "..\release\portable\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
