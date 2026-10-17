$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SetOutputToDefaultAudioDevice()
while ($null -ne ($requestLine = [Console]::ReadLine())) {
    try {
        $request = $requestLine | ConvertFrom-Json
        $available = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled })
        if ($request.action -eq 'voices') {
            $voiceNames = @($available | ForEach-Object { $_.VoiceInfo.Name + ' (' + $_.VoiceInfo.Culture.Name + ')' })
            @{ ok = $true; voices = $voiceNames } | ConvertTo-Json -Compress
        } else {
            $voice = $available | Where-Object { $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $request.language } | Select-Object -First 1
            if ($null -eq $voice) { throw ('No installed ' + $request.language + ' voice. Add the Windows speech voice or use DFPlayer recordings.') }
            $speaker.SelectVoice($voice.VoiceInfo.Name)
            $speaker.Speak([string]$request.text)
            @{ ok = $true; spoken = $request.text } | ConvertTo-Json -Compress
        }
    } catch {
        @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    }
}
$speaker.Dispose()
