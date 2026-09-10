Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class EnumWin {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool EnumWindows(Cb cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int c);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetClassName(IntPtr h, StringBuilder s, int c);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();

    public delegate bool Cb(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

[void][EnumWin]::SetProcessDPIAware()
$fg = [EnumWin]::GetForegroundWindow()
$script:items = @()

$callback = [EnumWin+Cb] {
    param($h, $p)
    if ([EnumWin]::IsWindowVisible($h)) {
        $title = New-Object System.Text.StringBuilder 512
        [void][EnumWin]::GetWindowText($h, $title, 512)
        $cls = New-Object System.Text.StringBuilder 256
        [void][EnumWin]::GetClassName($h, $cls, 256)
        $rect = New-Object EnumWin+RECT
        [void][EnumWin]::GetWindowRect($h, [ref]$rect)
        $t = $title.ToString()
        if ($t) {
            $script:items += [pscustomobject]@{
                Fg    = ($h -eq $fg)
                Title = $t
                Class = $cls.ToString()
                L     = $rect.Left
                T     = $rect.Top
                W     = $rect.Right - $rect.Left
                H     = $rect.Bottom - $rect.Top
            }
        }
    }
    return $true
}

[void][EnumWin]::EnumWindows($callback, [IntPtr]::Zero)

$script:items |
    Where-Object { $_.W -gt 200 } |
    Format-Table -AutoSize |
    Out-String -Width 220
