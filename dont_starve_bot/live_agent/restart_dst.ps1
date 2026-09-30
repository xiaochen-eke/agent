$exe = "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together\bin64\dontstarve_dedicated_server_nullrenderer_x64.exe"
$workdir = "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together\bin"
$token = "pds-g^KU_tny-dtuJ^lknwfFXTe8mmJB/24YAofNkjh3Au4V2IB5IVJr3QZJg=^iMT659NLrz6xMoMe"

$common = '-persistent_storage_root "APP:Klei/" -conf_dir DoNotStarveTogether -cluster Cluster_5 -ownernetid 76561199036267022 -ownerdir 1076001294 -clouddir 1076001294 -backup_log_count 25 -backup_log_period 0'

$masterArgs = $common + ' -shard Master -secondary_log_prefix master -sigprefix DST_Master -token "' + $token + '"'
$cavesArgs  = $common + ' -shard Caves -secondary_log_prefix caves -sigprefix DST_Secondary -token "' + $token + '"'

function Launch-Shard($argsStr) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.WorkingDirectory = $workdir
    $psi.Arguments = $argsStr
    $psi.UseShellExecute = $false
    [System.Diagnostics.Process]::Start($psi) | Out-Null
}

# 先停掉旧 shard，避免端口冲突（去掉 monitor_parent_process 后游戏不再随父进程自动退出）
Get-Process -Name "dontstarve_dedicated_server_nullrenderer_x64" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Launch-Shard $masterArgs
Start-Sleep -Seconds 2
Launch-Shard $cavesArgs
Write-Output "relaunched master + caves"
