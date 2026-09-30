$exe = "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together\bin64\dontstarve_dedicated_server_nullrenderer_x64.exe"
$workdir = "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together\bin"
$token = "pcl-sing^KU_tny-dtuJ^DontStarveTogether^9Y8He9nKQmpEcXxnY5+r5epVQcufGU1GW3YqFV7rUFE="

$common = '-monitor_parent_process 34184 -persistent_storage_root "APP:Klei/" -conf_dir DoNotStarveTogether -cluster Cluster_5 -ownernetid 76561199036267022 -ownerdir 1076001294 -clouddir 1076001294 -backup_log_count 25 -backup_log_period 0'

$cavesArgs = $common + ' -shard Caves -secondary_log_prefix caves -sigprefix DST_Secondary -token "' + $token + '"'

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.WorkingDirectory = $workdir
$psi.Arguments = $cavesArgs
$psi.UseShellExecute = $false
[System.Diagnostics.Process]::Start($psi) | Out-Null
Write-Output "relaunched caves only"
