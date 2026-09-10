param(
    [ValidateSet("window", "shot", "click", "keys", "focus", "move", "paste", "selectall", "scroll")]
    [string]$Action = "window",
    [string]$Title = "Mediiia",
    [string]$Path = "$env:TEMP\mp_shot.png",
    [int]$X = 0,
    [int]$Y = 0,
    [string]$Text = "",
    [string]$Class = "",
    [switch]$WindowOnly
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class U {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, uint e);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int c);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetClassName(IntPtr h, StringBuilder s, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(Cb cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);

    public delegate bool Cb(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    // Настоящее сочетание Ctrl+<key>: SendKeys не годится для Ctrl+V в Tk и диалогах.
    public static void CtrlKey(byte vk) {
        keybd_event(0x11, 0, 0, UIntPtr.Zero);          // Ctrl down
        System.Threading.Thread.Sleep(40);
        keybd_event(vk, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(40);
        keybd_event(vk, 0, 2, UIntPtr.Zero);            // key up
        System.Threading.Thread.Sleep(40);
        keybd_event(0x11, 0, 2, UIntPtr.Zero);          // Ctrl up
    }

    public static void Wheel(int x, int y, int notches) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(120);
        for (int i = 0; i < Math.Abs(notches); i++) {
            mouse_event(0x0800, 0, 0, (uint)(notches > 0 ? 120 : -120), 0);
            System.Threading.Thread.Sleep(60);
        }
    }

    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(150);
        mouse_event(0x0002, 0, 0, 0, 0);
        System.Threading.Thread.Sleep(70);
        mouse_event(0x0004, 0, 0, 0, 0);
    }
}
"@

[void][U]::SetProcessDPIAware()

$script:found = @()
$cb = [U+Cb] {
    param($h, $p)
    if ([U]::IsWindowVisible($h)) {
        $sb = New-Object System.Text.StringBuilder 512
        [void][U]::GetWindowText($h, $sb, $sb.Capacity)
        $t = $sb.ToString()
        if ($t -and $t -like "*$Title*") {
            $cn = New-Object System.Text.StringBuilder 256
            [void][U]::GetClassName($h, $cn, $cn.Capacity)
            $cls = $cn.ToString()
            if (-not $Class -or $cls -like "*$Class*") {
                $r = New-Object U+RECT
                [void][U]::GetWindowRect($h, [ref]$r)
                if ($r.Left -gt -10000) {
                    $script:found += [pscustomobject]@{
                        Handle = [int64]$h; Title = $t; Class = $cls
                        Left = $r.Left; Top = $r.Top
                        Width = $r.Right - $r.Left; Height = $r.Bottom - $r.Top
                    }
                }
            }
        }
    }
    return $true
}
[void][U]::EnumWindows($cb, [IntPtr]::Zero)
# Точное совпадение заголовка важнее размера: иначе «Mediiia» ловит вкладку Chrome.
$win = $script:found | Where-Object { $_.Title -eq $Title } | Select-Object -First 1
if (-not $win) {
    $win = $script:found | Sort-Object -Property Width -Descending | Select-Object -First 1
}

function Focus-Window {
    param($Window)
    if (-not $Window) { return }
    [void][U]::ShowWindow([IntPtr]$Window.Handle, 9)
    [void][U]::SetForegroundWindow([IntPtr]$Window.Handle)
    Start-Sleep -Milliseconds 450
}

function Save-Shot {
    param([string]$Out, $Window, [bool]$OnlyWindow)
    if ($OnlyWindow -and $Window) {
        $l = $Window.Left; $t = $Window.Top; $w = $Window.Width; $h = $Window.Height
    } else {
        $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
        $l = $b.Left; $t = $b.Top; $w = $b.Width; $h = $b.Height
    }
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($l, $t, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return "$Out ($w x $h at $l,$t)"
}

switch ($Action) {
    "window" {
        if (-not $win) { Write-Output "NOT_FOUND"; exit 1 }
        $win | Format-List | Out-String | Write-Output
    }
    "focus" {
        if (-not $win) { Write-Output "NOT_FOUND"; exit 1 }
        [void][U]::ShowWindow([IntPtr]$win.Handle, 9)
        [void][U]::SetForegroundWindow([IntPtr]$win.Handle)
        Start-Sleep -Milliseconds 500
        Write-Output "FOCUSED $($win.Title) at $($win.Left),$($win.Top) size $($win.Width)x$($win.Height)"
    }
    "shot" {
        if ($win) {
            [void][U]::ShowWindow([IntPtr]$win.Handle, 9)
            [void][U]::SetForegroundWindow([IntPtr]$win.Handle)
            Start-Sleep -Milliseconds 400
        }
        Write-Output (Save-Shot -Out $Path -Window $win -OnlyWindow:$WindowOnly.IsPresent)
        if ($win) { Write-Output "WINDOW $($win.Left),$($win.Top) $($win.Width)x$($win.Height)" }
    }
    "click" {
        if ($win) {
            [void][U]::ShowWindow([IntPtr]$win.Handle, 9)
            [void][U]::SetForegroundWindow([IntPtr]$win.Handle)
            Start-Sleep -Milliseconds 350
        }
        [U]::Click($X, $Y)
        Start-Sleep -Milliseconds 600
        Write-Output "CLICKED $X,$Y"
    }
    "scroll" {
        Focus-Window $win
        $notches = if ($Text) { [int]$Text } else { -5 }
        [U]::Wheel($X, $Y, $notches)
        Start-Sleep -Milliseconds 500
        Write-Output "SCROLLED $notches at $X,$Y"
    }
    "move" {
        if (-not $win) { Write-Output "NOT_FOUND"; exit 1 }
        $w = if ($Text) { [int]($Text.Split("x")[0]) } else { $win.Width }
        $h = if ($Text) { [int]($Text.Split("x")[1]) } else { $win.Height }
        [void][U]::MoveWindow([IntPtr]$win.Handle, $X, $Y, $w, $h, $true)
        Start-Sleep -Milliseconds 400
        Write-Output "MOVED to $X,$Y size ${w}x${h}"
    }
    "paste" {
        if ($Text) { Set-Clipboard -Value $Text }
        Focus-Window $win
        if ($X -gt 0 -and $Y -gt 0) { [U]::Click($X, $Y); Start-Sleep -Milliseconds 300 }
        [U]::CtrlKey(0x56)   # V
        Start-Sleep -Milliseconds 400
        Write-Output "PASTED"
    }
    "selectall" {
        Focus-Window $win
        if ($X -gt 0 -and $Y -gt 0) { [U]::Click($X, $Y); Start-Sleep -Milliseconds 300 }
        [U]::CtrlKey(0x41)   # A
        Start-Sleep -Milliseconds 250
        Write-Output "SELECTED"
    }
    "keys" {
        Focus-Window $win
        if ($X -gt 0 -and $Y -gt 0) { [U]::Click($X, $Y); Start-Sleep -Milliseconds 300 }
        [System.Windows.Forms.SendKeys]::SendWait($Text)
        Start-Sleep -Milliseconds 500
        Write-Output "TYPED"
    }
}
