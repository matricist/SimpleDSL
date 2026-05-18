# 파이프라인 강화

## 현재 상태

현재 프로그램은 DSL 파일을 입력으로 받아 다음 두 출력을 만든다.

- `.musicxml`
- `.svg`

예:

```powershell
dotnet run -- sample/empty-window.dsl sample/empty-window.musicxml sample/empty-window.svg
```

이 구조는 초기 검증에는 충분하지만, 실제 작곡 도구로 쓰려면 파이프라인을 더 명확하게 만들 필요가 있다.

## 확장 가능한 출력 포맷

### 1. MIDI

가장 먼저 추가할 만한 출력이다.

장점:

- 재생 확인이 빠르다.
- DAW로 가져가기 쉽다.
- AI 작곡 결과를 소리로 검증하기 좋다.

고려할 점:

- 표준 .NET만으로 MIDI 파일을 직접 작성할 수는 있지만, SMF 구조를 직접 구현해야 한다.
- tempo, note on/off, track chunk, delta time 처리가 필요하다.
- RH/LH를 별도 MIDI track으로 내보낼 수 있다.

### 2. MP3/WAV

사용자 입장에서는 가장 직관적인 결과물이다.

가능한 방식:

- DSL -> MIDI -> 외부 사운드폰트/신디사이저 -> WAV/MP3
- DSL -> MusicXML -> MuseScore CLI -> 오디오 렌더
- 앱 내부에 간단한 신디사이저 구현

현실적인 우선순위:

1. MIDI 출력
2. 외부 도구 연동으로 WAV 생성
3. MP3 인코딩

MP3는 인코딩 라이선스나 외부 도구 문제가 있을 수 있으므로, 처음에는 WAV가 더 단순하다.

### 3. PDF/PNG 악보

현재 SVG는 브라우저에서 보기 좋지만, 인쇄용 악보로는 제한적이다.

가능한 방식:

- SVG -> PDF 변환
- MusicXML -> MuseScore CLI -> PDF/PNG
- 자체 악보 렌더러 개선

현실적인 방향:

- 자체 SVG는 빠른 preview용으로 유지한다.
- 고품질 악보는 MusicXML을 외부 조판 엔진에 맡긴다.

### 4. 분석 리포트

DSL을 빌드할 때 다음 정보를 함께 출력할 수 있다.

- 총 마디 수
- 트랙별 마디 수
- 마디별 슬롯 검증 결과
- 음역 범위
- 사용된 pitch 목록
- 가장 긴 음
- 쉼표 밀도
- 섹션별 음 밀도

예:

```text
Build succeeded.
Measures: 48
Tracks: RH, LH
RH range: E4-C6
LH range: A1-A3
Warnings: 0
```

## 빌드 시스템처럼 만들기

지금은 단순 실행 방식이다.

```powershell
dotnet run -- input.dsl output.musicxml output.svg
```

나중에는 프로그래밍 언어처럼 명령을 나누는 것이 좋다.

후보:

```powershell
musicdsl build sample/empty-window.dsl
musicdsl check sample/empty-window.dsl
musicdsl render sample/empty-window.dsl --format svg
musicdsl export sample/empty-window.dsl --format musicxml
musicdsl play sample/empty-window.dsl
```

명령별 역할:

- `check`: 문법과 마디 수 검증
- `build`: 기본 산출물 전체 생성
- `render`: 악보 이미지 생성
- `export`: 특정 포맷 생성
- `play`: MIDI 또는 오디오 재생
- `watch`: 파일 변경 시 자동 빌드

## 프로젝트 파일 구조 제안

곡 하나가 커지면 `.dsl` 하나만으로 관리하기 어렵다.

후보 구조:

```text
songs/
  empty-window/
    brief.md
    score.dsl
    build.musicxml
    build.svg
    build.mid
    build-report.md
```

또는:

```text
musicdsl.json
```

예:

```json
{
  "input": "sample/empty-window.dsl",
  "outputs": ["musicxml", "svg", "midi"],
  "sound": {
    "instrument": "harpsichord"
  }
}
```

## GUI 방향

### WinForms

장점:

- Windows에서 빠르게 만들 수 있다.
- 파일 선택, 빌드 버튼, SVG preview 정도는 단순하다.
- C# 프로젝트와 잘 맞는다.

가능한 화면:

- 왼쪽: DSL editor
- 오른쪽: SVG 악보 preview
- 아래: diagnostics/build log
- 상단: Build, Play, Export buttons

### WPF 또는 Avalonia

나중에 더 보기 좋은 앱을 만들려면 WPF/Avalonia가 낫다.

하지만 초기에는 WinForms가 더 빠르다.

## 외부 도구 연동

### MuseScore CLI

MusicXML을 고품질 악보와 오디오로 바꾸는 데 유용하다.

가능한 출력:

- PDF
- PNG
- WAV
- MP3
- MIDI

고민할 점:

- 사용자의 PC에 MuseScore가 설치되어 있어야 한다.
- 경로 탐색과 에러 처리가 필요하다.
- 외부 의존성을 둘지 선택해야 한다.

### DAW 연동

초기 목표는 아니지만 MIDI 출력이 생기면 자연스럽게 가능해진다.

## 단기 우선순위

1. `check` 단계 추가
2. 마디 수/슬롯 수 diagnostics 출력
3. MIDI 출력 추가
4. build report 생성
5. MuseScore CLI 연동 실험
6. WinForms preview 앱 검토

## 장기 목표

Music DSL을 다음 흐름으로 발전시킨다.

```text
작곡 지시 md
  -> AI 또는 사람
  -> .dsl
  -> check
  -> build
  -> MusicXML / SVG / MIDI / WAV / PDF
  -> 악보 프로그램 또는 DAW
```

최종적으로는 단순 변환기가 아니라, 텍스트 기반 작곡 IDE에 가까운 도구가 되는 것이 목표다.
