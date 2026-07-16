Option Explicit

Dim shell, filesystem, runner, exitCode

Set filesystem = CreateObject("Scripting.FileSystemObject")
runner = filesystem.BuildPath(filesystem.GetParentFolderName(WScript.ScriptFullName), "run_symbol_maintenance_if_due.bat")

If Not filesystem.FileExists(runner) Then
    WScript.Quit 1
End If

Set shell = CreateObject("WScript.Shell")
exitCode = shell.Run(Chr(34) & runner & Chr(34), 0, True)
WScript.Quit exitCode
