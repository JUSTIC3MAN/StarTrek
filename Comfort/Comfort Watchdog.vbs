' Comfort Watchdog - Justice 2026-10-27. Keeps Comfort running so the GPU never sits idle.
' Every 30 s: if Comfort\heartbeat.txt (rewritten every 5 s by Comfort) is older than 90 s and
' Star Trek\Overseer\PAUSE does not exist, it starts Comfort.exe and writes a line in comfort.log.
' Runs hidden. On its first run it adds itself to the Windows Startup folder, so it starts at every login.
' To stop production on purpose: create the file Overseer\PAUSE (the watchdog then leaves Comfort closed).
Option Explicit
Dim sh, fs, base, pauseF, hb, logF, exe, lastStart, lnk, sc
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = "A:\Ai projects\Star Trek\Comfort"
pauseF = "A:\Ai projects\Star Trek\Overseer\PAUSE"
hb = base & "\heartbeat.txt"
logF = base & "\comfort.log"
exe = base & "\Comfort.exe"
If AlreadyRunning() Then WScript.Quit
lnk = sh.SpecialFolders("Startup") & "\Comfort Watchdog.lnk"
If Not fs.FileExists(lnk) Then
  Set sc = sh.CreateShortcut(lnk)
  sc.TargetPath = "wscript.exe"
  sc.Arguments = """" & WScript.ScriptFullName & """"
  sc.WorkingDirectory = base
  sc.Save
  LogLine "watchdog: added to the Windows Startup folder"
End If
LogLine "watchdog: running (checks Comfort every 30 s)"
lastStart = DateAdd("n", -10, Now)
Do
  If Not fs.FileExists(pauseF) Then
    If Stale() And DateDiff("s", lastStart, Now) > 180 Then
      LogLine "watchdog: Comfort was not running (heartbeat stale) - starting Comfort.exe"
      sh.Run """" & exe & """", 1, False
      lastStart = Now
    End If
  End If
  WScript.Sleep 30000
Loop

Function Stale()
  Stale = True
  If fs.FileExists(hb) Then
    If DateDiff("s", fs.GetFile(hb).DateLastModified, Now) < 90 Then Stale = False
  End If
End Function

Sub LogLine(msg)
  On Error Resume Next
  Dim f
  Set f = fs.OpenTextFile(logF, 8, True)
  f.WriteLine Year(Now) & "-" & Right("0" & Month(Now), 2) & "-" & Right("0" & Day(Now), 2) & " " & Right("0" & Hour(Now), 2) & ":" & Right("0" & Minute(Now), 2) & ":" & Right("0" & Second(Now), 2) & " " & msg
  f.Close
End Sub

Function AlreadyRunning()
  Dim w, p, n
  n = 0
  Set w = GetObject("winmgmts:\\.\root\cimv2")
  For Each p In w.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE Name='wscript.exe'")
    If Not IsNull(p.CommandLine) Then
      If InStr(1, p.CommandLine, "Comfort Watchdog.vbs", 1) > 0 Then n = n + 1
    End If
  Next
  AlreadyRunning = (n > 1)
End Function
