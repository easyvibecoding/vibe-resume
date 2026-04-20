<#
.SYNOPSIS
    Periodically mirror ~/.claude/projects to a persistent archive on Windows.

.DESCRIPTION
    Claude Code purges session JSONL transcripts older than 30 days by default.
    Run this weekly (via Task Scheduler) so the history you built up stays on
    disk long enough to feed into `vibe-resume` even if you miss a window.

    Mirrors $env:USERPROFILE\.claude\projects to <ArchiveDir>\current using
    robocopy's /MIR semantics but with /XO (exclude older) so an archived
    transcript is never overwritten by a shorter source file. A dated hardlink
    snapshot is then written to <ArchiveDir>\snapshots\yyyy-MM-dd.

.PARAMETER ArchiveDir
    Destination root. Defaults to $HOME\ClaudeCodeArchive.

.EXAMPLE
    PS> .\backup_claude_projects.ps1
    Uses the default archive path; logs are printed to the host.

.EXAMPLE
    PS> .\backup_claude_projects.ps1 -ArchiveDir D:\Backups\Claude -WhatIf
    Dry run - shows what would be copied without touching disk. Also works
    on macOS/Linux via pwsh for smoke-testing this script.

.NOTES
    Install as a scheduled task:
        schtasks /Create /TN "vibe-resume backup" /XML scripts\vibe-resume-backup.xml
    or import scripts\vibe-resume-backup.xml via the Task Scheduler GUI
    (Action > Import Task...).
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ArchiveDir = (Join-Path $HOME 'ClaudeCodeArchive')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Claude Code uses the same .claude/projects path on every OS.
$src = Join-Path $HOME '.claude/projects'
$timestamp = Get-Date -Format 'yyyy-MM-dd'
$current = Join-Path $ArchiveDir 'current'
$snapshot = Join-Path $ArchiveDir (Join-Path 'snapshots' $timestamp)

if (-not (Test-Path $src)) {
    Write-Warning "Source not found: $src"
    Write-Warning 'Nothing to back up - is Claude Code installed on this machine?'
    return
}

if ($PSCmdlet.ShouldProcess($ArchiveDir, 'Create archive directory tree')) {
    New-Item -ItemType Directory -Force -Path $current | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $snapshot) | Out-Null
}

function Invoke-Mirror {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([string]$From, [string]$To)

    # robocopy is Windows-only; fall back to Copy-Item recursion elsewhere so
    # this script can be smoke-tested on macOS/Linux with pwsh.
    if ($IsWindows) {
        # /MIR = mirror; /XO = skip older (archive wins over source if source was truncated)
        # /XD = exclude dirs we don't want in the archive; /R:2 /W:5 = quick retries
        # /NFL /NDL /NP = quieter console output
        $robocopyArgs = @($From, $To, '/MIR', '/XO', '/XF', '*.tmp', '/R:2', '/W:5', '/NFL', '/NDL', '/NP')
        if ($WhatIfPreference) { $robocopyArgs += '/L' }
        & robocopy @robocopyArgs | Out-Host
        # robocopy exit codes 0-7 indicate success/no-op; >=8 is a real failure.
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed with exit code $LASTEXITCODE"
        }
    }
    else {
        if ($PSCmdlet.ShouldProcess($To, "Mirror $From (Copy-Item fallback, non-Windows)")) {
            Copy-Item -Path (Join-Path $From '*') -Destination $To -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# Information stream carries user-facing log lines; callers can silence with
# -InformationAction Ignore or capture via $InformationPreference = 'Continue'.
$InformationPreference = 'Continue'

Write-Information "Backing up $src -> $current"
Invoke-Mirror -From $src -To $current

if (Test-Path $current) {
    if ($PSCmdlet.ShouldProcess($snapshot, 'Write dated snapshot')) {
        Copy-Item -Path $current -Destination $snapshot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Information ''
Write-Information "Archive root: $ArchiveDir"
Write-Information 'Transcripts per month (current mirror):'

if (Test-Path $current) {
    Get-ChildItem -Path $current -Filter '*.jsonl' -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/]subagents[\\/]' } |
        Group-Object { $_.LastWriteTime.ToString('yyyy-MM') } |
        Sort-Object Name |
        ForEach-Object { "  {0,8}  {1}" -f $_.Count, $_.Name } |
        Write-Information
}
