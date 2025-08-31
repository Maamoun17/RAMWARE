; -- SETUP.ISS --
[Setup]
AppName=RamWare
AppVersion=1.0
DefaultDirName={pf}\RamWare
DefaultGroupName=RamWare
OutputDir=.\Installer
OutputBaseFilename=RamWare_Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=.\app_icon.ico

[Files]
Source: "dist\RamWare.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\RamWare"; Filename: "{app}\RamWare.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{commondesktop}\RamWare"; Filename: "{app}\RamWare.exe"; IconFilename: "{app}\app_icon.ico"