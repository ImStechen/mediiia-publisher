# Управление окнами Windows: скриншот, поиск окна, клик, ввод текста.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not ("WinUi" -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class WinUi {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }

    public const uint LEFTDOWN = 0x0002;
    public const uint LEFTUP = 0x0004;

    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(120);
        mouse_event(LEFTDOWN, 0, 0, 0, 0);
        System.Threading.Thread.Sleep(60);
        mouse_event(LEFTUP, 0, 0, 0, 0);
    }
}
"@
}

function Find-AppWindow {
    param([string]$TitlePart)
    $result = @()
    $callback = [WinUi+EnumWindowsProc]{
        param($hWnd, $lParam)
        if ([WinUi]::IsWindowVisible($hWnd)) {
            $sb = New-Object System.Text.StringBuilder 512
            [void][WinUi]::GetWindowText($hWnd, $sb, $sb.Capacity)
            $title = $sb.ToString()
            if ($title -and $title -like "*$TitlePart*") {
                $rect = New-Object WinUi+RECT
                [void][WinUi]::GetWindowRect($hWnd, [ref]$rect)
                $script:foundWindows += [pscustomobject]@{
                    Handle = $hWnd
                    Title  = $title
                    Left   = $rect.Left
                    Top    = $rect.Top
                    Right  = $rect.Right
                    Bottom = $rect.Bottom
                }
            }
        }
        return $true
    }
    $script:foundWindows = @()
    [void][WinUi]::EnumWindows($callback, [IntPtr]::Zero)
    return $script:foundWindows
}

function Focus-AppWindow {
    param([IntPtr]$Handle)
    [void][WinUi]::ShowWindow($Handle, 9)   # SW_RESTORE
    [void][WinUi]::SetForegroundWindow($Handle)
    Start-Sleep -Milliseconds 400
}

function Save-Screenshot {
    param([string]$Path, [int]$Left = 0, [int]$Top = 0, [int]$Width = 0, [int]$Height = 0)
    if ($Width -le 0 -or $Height -le 0) {
        $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $Left = $bounds.Left; $Top = $bounds.Top
        $Width = $bounds.Width; $Height = $bounds.Height
    }
    $bmp = New-Object System.Drawing.Bitmap $Width, $Height
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.CopyFromScreen($Left, $Top, 0, 0, (New-Object System.Drawing.Size $Width, $Height))
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $gfx.Dispose(); $bmp.Dispose()
    return $Path
}

function Send-Text {
    param([string]$Text)
    [System.Windows.Forms.SendKeys]::SendWait($Text)
    Start-Sleep -Milliseconds 250
}
