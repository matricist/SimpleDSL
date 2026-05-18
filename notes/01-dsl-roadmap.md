# DSL 손봐야 할 부분

## 목표

Music DSL을 단순 텍스트 포맷에서 작곡용 미니 언어로 발전시킨다.

현재 DSL은 `;` 기반 슬롯과 `PitchOctave-DurationSlots` 표기로 작동하지만, 사람이 긴 곡을 쓰거나 AI가 안정적으로 생성하기에는 검증 도구와 구조적 문법이 더 필요하다.

## 우선 해결할 문제

### 1. 마디 길이 검증

현재는 한 마디가 정확히 16 슬롯인지 사람이 직접 세야 한다.

필요한 기능:

- `@time: 4/4`, `@unit: 1/16` 기준으로 한 마디 슬롯 수 계산
- 각 트랙의 마디별 `;` 개수 검증
- RH/LH의 총 마디 수 불일치 감지
- 마디가 짧거나 길면 컴파일 에러 출력
- 에러 메시지에 파일, 트랙, 마디 번호, 예상 슬롯 수, 실제 슬롯 수 표시

예:

```text
Error: RH measure 12 has 20 slots, expected 16.
```

### 2. 명시적 마디 구분

세미콜론만으로 긴 곡을 쓰면 마디 경계가 잘 보이지 않는다.

후보 문법:

```text
| C5-2;;D5-2;;E5-4;;;; |
```

또는:

```text
@measure 12
C5-2;;D5-2;;E5-4;;;;
```

고민할 점:

- `|`는 악보 관습과 잘 맞는다.
- 기존 DSL과 호환하려면 `|`는 선택적 구분자로 처리하는 것이 좋다.
- VS Code 확장에서 마디 단위 색상 표시를 하려면 명시적 구분자가 있으면 훨씬 편하다.

### 3. 주석 공식 지원

현재 parser는 `//` 인라인 주석을 일부 처리하지만, DSL 명세에는 아직 포함되어 있지 않다.

정식 지원 후보:

```text
// A section
C5-2;;D5-2;;
```

```text
/* longer comment */
```

우선순위:

- 1차: 한 줄 주석 `//`
- 2차: 블록 주석

### 4. 섹션 문법

긴 곡에서는 `A`, `A'`, `B`, `Outro` 같은 구조가 필요하다.

후보:

```text
@section: A
@measures: 1-12
```

또는:

```text
#section A 1-12
```

필요한 정보:

- 섹션 이름
- 시작/끝 마디
- 에너지 레벨
- 작곡 의도

### 5. 음 길이와 슬롯 이동의 혼동 줄이기

현재 `C5-8;;;;;;;;`처럼 음 길이와 커서 이동을 따로 써야 한다.

장점:

- 시작 시점과 지속시간이 분리되어 화음 표현이 쉽다.

단점:

- 사람이 마디 길이를 세기 어렵다.
- 긴 음 뒤에 세미콜론을 과하게 넣기 쉽다.

개선 후보:

```text
C5-8 @advance 8
```

또는 마디 내부를 슬롯 배열처럼 쓰는 문법:

```text
[ C5-8 . . . . . . . ]
```

당장은 기존 문법을 유지하고, validator와 editor 지원으로 보완하는 편이 안전하다.

## VS Code Extension 아이디어

### 1. 문법 하이라이트

- metadata: `@title`, `@track`, `@tempo`
- pitch: `C5`, `D#5`, `Bb3`
- duration: `-4`, `-8`
- cursor: `;`
- measure bar: `|`
- comments: `//`

### 2. 마디별 배경색

- 홀수 마디와 짝수 마디 배경색 다르게 표시
- RH/LH 같은 마디를 같은 색으로 표시
- 마디가 길거나 짧으면 붉은 배경 표시

### 3. Diagnostics

컴파일 전에 에디터에서 바로 경고 표시:

- 알 수 없는 음 이름
- 지원하지 않는 트랙
- 잘못된 duration
- 한 마디 슬롯 수 불일치
- RH/LH 마디 수 불일치
- note duration이 0 이하

### 4. Preview

- 현재 파일을 저장하면 자동으로 SVG preview 갱신
- MusicXML export 버튼
- 나중에는 MIDI/MP3 preview까지 연결

## 컴파일러 관점에서 필요한 단계

1. Tokenize
2. Parse
3. Build AST
4. Semantic validation
5. Normalize tracks into measure model
6. Export to target formats

현재 구현은 Parse와 Export가 바로 연결되어 있으므로, 중간에 `Measure`, `Voice`, `Diagnostic` 모델을 추가하는 것이 다음 구조 개선 포인트다.
