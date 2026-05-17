#define MyAppName "Spectrum Hub"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Spectrum"
#ifndef SourceDir
#define SourceDir "..\dist\SpectrumHub"
#endif
#ifndef OutputDir
#define OutputDir "..\dist\installer"
#endif
#ifndef IconFile
#define IconFile "..\packages\cli\src\spectrum_cli\assets\spec-icon.ico"
#endif

[Setup]
AppId={{A0D9A1BA-5B79-4CF6-B130-9D5B306F1207}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SpectrumHub
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=SpectrumHubSetup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\SpectrumHub.exe
SetupIconFile={#IconFile}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Spectrum Hub"; Filename: "{app}\SpectrumHub.exe"
Name: "{autodesktop}\Spectrum Hub"; Filename: "{app}\SpectrumHub.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SpectrumHub.exe"; Description: "Launch Spectrum Hub"; Flags: shellexec nowait postinstall skipifsilent
