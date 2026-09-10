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
OutputBaseFilename=MediiiaPublisher-WebSetup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked

[Dirs]
Name: "{app}"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
const
  PortableUrl = 'https://github.com/ImStechen/mediiia-publisher/releases/latest/download/MediiiaPublisher-portable.zip';

procedure CurStepChanged(CurStep: TSetupStep);
var
  ArchivePath: String;
  PowerShellPath: String;
  Params: String;
  ResultCode: Integer;
begin
  if CurStep <> ssInstall then
    exit;

  WizardForm.StatusLabel.Caption := 'Скачиваю последнюю версию с GitHub...';
  ArchivePath := ExpandConstant('{tmp}\MediiiaPublisher-portable.zip');
  DownloadTemporaryFile(PortableUrl, 'MediiiaPublisher-portable.zip', '', nil);

  WizardForm.StatusLabel.Caption := 'Распаковываю приложение...';
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Params :=
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ' +
    AddQuotes(
      'Expand-Archive -LiteralPath ' + AddQuotes(ArchivePath) +
      ' -DestinationPath ' + AddQuotes(ExpandConstant('{app}')) + ' -Force'
    );
  if not Exec(PowerShellPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    RaiseException('Не удалось запустить распаковку.');
  if ResultCode <> 0 then
    RaiseException(Format('Распаковка завершилась с кодом %d.', [ResultCode]));
  if not FileExists(ExpandConstant('{app}\{#MyAppExeName}')) then
    RaiseException('После распаковки не найден файл приложения.');
end;
