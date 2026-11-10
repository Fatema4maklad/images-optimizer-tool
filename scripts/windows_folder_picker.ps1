param([switch]$SelfTest)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# PowerShell 5 runs on .NET Framework, whose FolderBrowserDialog uses the old
# tree view. IFileDialog with FOS_PICKFOLDERS opens the standard Explorer UI.
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;

[ComImport]
[Guid("42f85136-db7e-439c-85f1-e4075d135fc8")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IFileDialog
{
    [PreserveSig] int Show(IntPtr owner);
    void SetFileTypes(uint count, IntPtr filterSpec);
    void SetFileTypeIndex(uint index);
    void GetFileTypeIndex(out uint index);
    void Advise(IntPtr events, out uint cookie);
    void Unadvise(uint cookie);
    void SetOptions(uint options);
    void GetOptions(out uint options);
    void SetDefaultFolder(IShellItem folder);
    void SetFolder(IShellItem folder);
    void GetFolder(out IShellItem folder);
    void GetCurrentSelection(out IShellItem item);
    void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string name);
    void GetFileName(out IntPtr name);
    void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string title);
    void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string label);
    void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string label);
    void GetResult(out IShellItem item);
    void AddPlace(IShellItem item, int placement);
    void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string extension);
    void Close(int result);
    void SetClientGuid(ref Guid guid);
    void ClearClientData();
    void SetFilter(IntPtr filter);
}

[ComImport]
[Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IShellItem
{
    void BindToHandler(IntPtr context, ref Guid handler, ref Guid interfaceId, out IntPtr result);
    void GetParent(out IShellItem parent);
    void GetDisplayName(uint format, out IntPtr name);
    void GetAttributes(uint mask, out uint attributes);
    void Compare(IShellItem item, uint hint, out int order);
}

public static class ModernFolderPicker
{
    private const uint PickFolders = 0x20;
    private const uint ForceFileSystem = 0x40;
    private const uint FileSystemPath = 0x80058000;
    private const int Cancelled = unchecked((int)0x800704C7);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    private static extern void SHCreateItemFromParsingName(
        string path, IntPtr context, ref Guid interfaceId,
        [MarshalAs(UnmanagedType.Interface)] out IShellItem item);

    public static string Select(string initialFolder, IntPtr owner)
    {
        Type dialogType = Type.GetTypeFromCLSID(
            new Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7"));
        IFileDialog dialog = (IFileDialog)Activator.CreateInstance(dialogType);
        IShellItem initialItem = null;
        IShellItem selectedItem = null;
        IntPtr pathPointer = IntPtr.Zero;
        try
        {
            uint options;
            dialog.GetOptions(out options);
            dialog.SetOptions(options | PickFolders | ForceFileSystem);
            dialog.SetTitle("Choose where processed image folders will be saved");
            dialog.SetOkButtonLabel("Select Folder");

            if (!String.IsNullOrWhiteSpace(initialFolder) && Directory.Exists(initialFolder))
            {
                Guid shellItemId = typeof(IShellItem).GUID;
                SHCreateItemFromParsingName(
                    initialFolder, IntPtr.Zero, ref shellItemId, out initialItem);
                dialog.SetDefaultFolder(initialItem);
            }

            int result = dialog.Show(owner);
            if (result == Cancelled)
                return null;
            Marshal.ThrowExceptionForHR(result);

            dialog.GetResult(out selectedItem);
            selectedItem.GetDisplayName(FileSystemPath, out pathPointer);
            return Marshal.PtrToStringUni(pathPointer);
        }
        finally
        {
            if (pathPointer != IntPtr.Zero)
                Marshal.FreeCoTaskMem(pathPointer);
            if (selectedItem != null)
                Marshal.ReleaseComObject(selectedItem);
            if (initialItem != null)
                Marshal.ReleaseComObject(initialItem);
            Marshal.ReleaseComObject(dialog);
        }
    }
}
'@

if ($SelfTest) {
    [ModernFolderPicker].FullName
    return
}

Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
try {
    $selected = [ModernFolderPicker]::Select(
        $env:IMAGE_SEO_INITIAL_FOLDER, $owner.Handle)
    if ($selected) {
        Write-Output $selected
    }
}
finally {
    $owner.Dispose()
}
