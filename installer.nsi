; 视频字幕工具 - NSIS 安装脚本
; 用于创建专业的 Windows 安装程序
;
; 使用方法：
; 1. 安装 NSIS: winget install NSIS.NSIS
; 2. 编译此脚本: makensis installer.nsi

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ── 应用信息 ────────────────────────────────────────────────────────────
!define APP_NAME "视频字幕工具"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Video Subtitle Tool"
!define APP_EXE "视频字幕工具.exe"
!define APP_GUID "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"

; ── 安装目录 ────────────────────────────────────────────────────────────
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "Install_Dir"
RequestExecutionLevel admin

; ── 界面设置 ────────────────────────────────────────────────────────────
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\wizard.bmp"

; ── 页面 ────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ── 语言 ────────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"

; ── 安装逻辑 ────────────────────────────────────────────────────────────
Section "主程序" SecMain
    SectionIn RO
    
    SetOutPath "$INSTDIR"
    
    ; 复制可执行文件
    File "dist\${APP_EXE}"
    
    ; 创建下载目录
    CreateDirectory "$INSTDIR\downloads"
    
    ; 写入注册表
    WriteRegStr HKLM "Software\${APP_NAME}" "Install_Dir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    
    ; 创建卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; 创建开始菜单快捷方式
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\卸载.lnk" "$INSTDIR\uninstall.exe"
    
    ; 创建桌面快捷方式
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    
SectionEnd

; ── FFmpeg 检测（可选）────────────────────────────────────────────────────
Section "检测 FFmpeg" SecFFmpeg
    ; 检查 FFmpeg 是否在 PATH 中
    nsExec::ExecToStack 'ffmpeg -version'
    Pop $0
    Pop $1
    
    ${If} $0 != 0
        MessageBox MB_YESNO "未检测到 FFmpeg，是否打开下载页面？" IDYES download
        Goto done
        
        download:
            ExecShell "open" "https://www.gyan.dev/ffmpeg/builds/"
        
        done:
    ${EndIf}
SectionEnd

; ── 卸载逻辑 ────────────────────────────────────────────────────────────
Section "Uninstall"
    ; 删除文件
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\uninstall.exe"
    
    ; 删除下载目录（如果为空）
    RMDir "$INSTDIR\downloads"
    
    ; 删除安装目录
    RMDir "$INSTDIR"
    
    ; 删除快捷方式
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\卸载.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    
    ; 删除注册表
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKLM "Software\${APP_NAME}"
SectionEnd

; ── 初始化 ────────────────────────────────────────────────────────────────
Function .onInit
    ; 检查是否已安装
    ReadRegStr $0 HKLM "Software\${APP_NAME}" "Install_Dir"
    ${If} $0 != ""
        MessageBox MB_YESNO "检测到已安装 ${APP_NAME}，是否覆盖安装？" IDYES proceed
        Abort
        
        proceed:
            ; 静默卸载旧版本
            ExecWait '"$0\uninstall.exe" /S _?=$0'
    ${EndIf}
FunctionEnd
