param([string]$Base = "http://192.168.0.133")
$ErrorActionPreference = "Stop"
$script:fail = 0

function Post($path, $body) { Invoke-RestMethod -Method Post -Uri "$Base$path" -Body $body -TimeoutSec 10 }
function Get-State { Invoke-RestMethod -Uri "$Base/api/state" -TimeoutSec 10 }

# expect = "fan,heater,humidifier,compressor" as 1/0
function Check($label, $state, $expect) {
  $got = ($state.relays | ForEach-Object { if ($_.on) { 1 } else { 0 } }) -join ","
  $why = ($state.relays | ForEach-Object { "$($_.name)=$($_.reason)" }) -join "; "
  if ($got -eq $expect) { "PASS  $label  [$got]" }
  else { $script:fail++; "FAIL  $label  expected [$expect] got [$got]  ($why)" }
}
function Sim($t, $h) { Post "/api/sim" @{ temp = $t; hum = $h } }

# Wait for the board
$deadline = (Get-Date).AddSeconds(45)
while ($true) { try { Get-State | Out-Null; break } catch { if ((Get-Date) -gt $deadline) { throw "board not reachable at $Base" }; Start-Sleep 2 } }

# Fast settings for testing
Post "/api/sim" @{ react = 0; fault = 0; temp = 22; hum = 50 } | Out-Null
Post "/api/settings" @{ mode = "auto"; tempSet = 22; humSet = 50; tempBand = 0.5; humBand = 3; compMinOff = 0; compMinOn = 0; fanRunOn = 2; fanMode = "auto" } | Out-Null
Start-Sleep 3

"--- temperature ---"
Check "T22.0 H50 all off"            (Sim 22 50)   "0,0,0,0"
Check "T22.6 cool"                   (Sim 22.6 50) "1,0,0,1"
Check "T22.2 still cooling"          (Sim 22.2 50) "1,0,0,1"
Check "T22.0 cool stops, fan run-on" (Sim 22.0 50) "1,0,0,0"
Start-Sleep 3
Check "run-on finished"              (Get-State)   "0,0,0,0"
Check "T21.4 heat"                   (Sim 21.4 50) "1,1,0,0"
Check "T21.8 still heating"          (Sim 21.8 50) "1,1,0,0"
Check "T22.0 heat stops"             (Sim 22.0 50) "1,0,0,0"

"--- humidity ---"
Check "H46 humidify"                 (Sim 22 46)   "1,0,1,0"
Check "H49 still humidifying"        (Sim 22 49)   "1,0,1,0"
Check "H50 humidify stops"           (Sim 22 50)   "1,0,0,0"

"--- dehumidify with reheat ---"
Check "H54 T22.0 comp + reheat"      (Sim 22.0 54) "1,1,0,1"
Check "T22.3 reheat holds"           (Sim 22.3 54) "1,1,0,1"
Check "T22.6 reheat off, comp on"    (Sim 22.6 54) "1,0,0,1"
Check "T22.2 still cooling, no heat" (Sim 22.2 54) "1,0,0,1"
Check "T22.0 reheat back on"         (Sim 22.0 54) "1,1,0,1"
Check "H50 all stop, run-on"         (Sim 22.0 50) "1,0,0,0"

"--- mixed and fault ---"
Check "T25 H40 comp + humidifier"    (Sim 25 40)   "1,0,1,1"
Check "sensor fault stops all"       (Post "/api/sim" @{ fault = 1 }) "1,0,0,0"
$s = Get-State
if ($s.demand.sensorFault) { "PASS  sensorFault flag set" } else { $script:fail++; "FAIL  sensorFault flag not set" }
Post "/api/sim" @{ fault = 0; temp = 22; hum = 50 } | Out-Null

"--- compressor protection (rest 5 s, min run 3 s) ---"
Post "/api/settings" @{ compMinOff = 5; compMinOn = 3 } | Out-Null
Start-Sleep 6
Check "T22.6 comp starts"            (Sim 22.6 50) "1,0,0,1"
$s = Sim 22.0 50
Check "T22.0 min run holds comp"     $s "1,0,0,1"
"      reason: $($s.relays[3].reason)"
Start-Sleep 4
Check "after min run + run-on, all off" (Get-State) "0,0,0,0"
$s = Sim 22.6 50
Check "restart blocked while resting" $s "0,0,0,0"
"      reason: $($s.relays[3].reason), rest left $($s.compRestLeft)s"
Start-Sleep 6
Check "starts after rest"            (Get-State)   "1,0,0,1"

"--- manual mode ---"
Post "/api/sim" @{ temp = 22; hum = 50 } | Out-Null
Post "/api/settings" @{ compMinOff = 0; compMinOn = 0 } | Out-Null
Check "manual: loads off, fan run-on" (Post "/api/settings" @{ mode = "manual" }) "1,0,0,0"
Start-Sleep 3
Check "manual: fan only"             (Post "/api/manual" @{ ch = 1; state = "on" }) "1,0,0,0"
Check "manual: heater forces fan"    (Post "/api/manual" @{ ch = 2; state = "on" }) "1,1,0,0"
Check "manual: fan switch off, still on" (Post "/api/manual" @{ ch = 1; state = "off" }) "1,1,0,0"
Check "manual: compressor"           (Post "/api/manual" @{ ch = 4; state = "on" }) "1,1,0,1"
Check "mode off: all stop, run-on"   (Post "/api/settings" @{ mode = "off" }) "1,0,0,0"
try { Post "/api/manual" @{ ch = 1; state = "on" } | Out-Null; $script:fail++; "FAIL  manual accepted outside Manual mode" }
catch { "PASS  manual rejected outside Manual mode" }

# Back to safe defaults
Post "/api/settings" @{ mode = "off"; compMinOff = 180; compMinOn = 60; fanRunOn = 30 } | Out-Null
Post "/api/sim" @{ temp = 22; hum = 50; react = 0; fault = 0 } | Out-Null
""
if ($script:fail -eq 0) { "ALL PASSED" } else { "$($script:fail) FAILED" }

