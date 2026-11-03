// Strings for the public results page (/benchmark). Spread into `en` / `ta` in strings.ts.
// No number is written here: every {placeholder} is filled from src/benchmark/summary.json, which
// scripts/build_benchmark_summary.py builds from the committed reports (tests/test_benchmark_summary.py).
// Copy rules: say "matches the editors' restoration", never call a restoration correct; no "experimental".

export const enBench = {
  'bench.kicker': 'Results',
  'bench.title': 'Benchmark results',
  'bench.lede':
    'How often Ezhuthu restores lost letters the way the editors did, measured on {n} gaps from {ins} inscriptions it was never tuned on. Every number links to the report it comes from. The headline numbers are for the pre-rank version the app ran before it switched to the fine-tuned Strands Decider; the live version has not been scored this way yet.',
  'bench.statTop1': 'First proposal matches the editors’ restoration',
  'bench.statTop1Sub': '{k} of {n} test gaps',
  'bench.statFill': 'Of the gaps it chooses to fill, these match',
  'bench.statFillSub': '{k} of {n} fills; it fills {cov} of gaps',
  'bench.statLong': 'Gaps of 4 or more letters',
  'bench.statLongSub': 'matches on {n} long gaps: still hard',

  'bench.lbTitle': 'Leaderboard on the test gaps',
  'bench.lbLede':
    'Top-1: how often the first proposal matches the editors’ restoration. The thin line on each bar is its 95% interval. The test gaps were scored once, after every choice had been made on the validation gaps.',
  'bench.subsetFull': 'All {n} gaps',
  'bench.subsetHard': 'Hard gaps ({n})',
  'bench.subsetHardHint':
    'Hard gaps have no close parallel in another training inscription, so copying a set phrase does not help.',
  'bench.sys.deployed': 'Ezhuthu, pre-rank version',
  'bench.sys.deployedD': 'Sonnet 4.6, Opus 4.6 for harder gaps, re-ranked with a character 5-gram; what the app ran before the fine-tuned decider',
  'bench.sys.ngram': 'Character 5-gram',
  'bench.sys.ngramD': 'Predicts letters from the training texts alone; no AI model',
  'bench.sys.routed2b': 'Routed with a local 2B decider',
  'bench.sys.routed2bD': 'The pipeline measured in PR #31, before the pre-rank version',
  'bench.sys.copy': 'Copy the best parallel',
  'bench.sys.copyD': 'Copies the matching passage from another inscription',
  'bench.sys.sonnet': 'Sonnet 4.6 alone',
  'bench.sys.sonnetD': 'One model, no escalation and no 5-gram',
  'bench.colSystem': 'System',
  'bench.colTop1': 'Top-1 [95% interval]',
  'bench.colMatches': 'Matches',
  'bench.colVs': 'Against the pre-rank version',
  'bench.vs': 'only pre-rank {a}, only this {b}; p {p}',
  'bench.vsSelf': 'reference',
  'bench.vsNone': 'not tested in the reports',
  'bench.vsNote':
    'p is an exact McNemar test on the same gaps, counting the gaps only one of the two systems matched. Below 0.05, the difference is unlikely to be chance.',
  'bench.source': 'Source',

  'bench.stopTitle': 'Knowing when to stop',
  'bench.stopBody':
    'Ezhuthu may leave a gap open instead of guessing. At confidence thresholds fitted on the validation gaps, it fills {cov} of the test gaps, and {acc} of those fills match the editors’ restoration ({k} of {n}). The gaps it leaves open go to an expert.',
  'bench.relTitle': 'Does its confidence mean what it says?',
  'bench.relBody':
    'Each bar groups the {n} test gaps by the confidence Ezhuthu gave; its height is how often those gaps matched. Bars close to the dashed line mean a stated 70% matches about 70% of the time.',
  'bench.ece': 'Average distance from the line (ECE): {ece}. Lower is better; 0 would be perfect.',
  'bench.relChart': 'Confidence against how often the first proposal matched, test gaps',
  'bench.relAxis': 'Confidence (%) across, share matched (%) up',

  'bench.gapTitle': 'Where it fails: long gaps',
  'bench.gapBody':
    'Most test gaps are a single letter, and there it does well. When four or more letters are lost its top-1 is only {x}, the same as copying a parallel ({c}). Long restorations still need an epigraphist.',
  'bench.colGap': 'Lost letters',
  'bench.colGaps': 'Gaps',
  'bench.gap.1 letter': '1 letter',
  'bench.gap.2-3 letters': '2 or 3 letters',
  'bench.gap.4+ letters': '4 or more letters',

  'bench.ocrTitle': 'Reading photos',
  'bench.ocrBody':
    'Character error rate: the share of letters the reader gets wrong, so lower is better. The Tamil-script plates are drawn from test-split lines in a modern font on a stone texture; real old letter shapes are harder.',
  'bench.ocr.clean': 'Tamil script, clean ({n} plates)',
  'bench.ocr.photo': 'Tamil script, photo-like ({n} plates)',
  'bench.ocr.weathered': 'Tamil script, weathered ({n} plates)',
  'bench.ocr.printed': 'Printed Tamil pages ({n} real scans)',
  'bench.ocr.brahmi': 'Tamil-Brahmi ({n} real photos)',
  'bench.ocrFail':
    'Tamil-Brahmi is not read: on {n} real photos of the Jambai inscription the error rate is {x}. The app warns whenever the script looks like Tamil-Brahmi, Vatteluttu or Grantha. Vatteluttu is not measured at all.',
  'bench.ocrChart': 'Character error rate of the photo reader by condition',

  'bench.decTitle': 'The Strands Decider: an honest negative result',
  'bench.dec1':
    'We tried the hosted Strands Decider (v19) as the step that picks a fill. On the {n} validation gaps set aside for it, it matched {a} against {b} for the setup without it ({x} and {y} gaps where only one matched, p = {p}): a tie.',
  'bench.dec2':
    'It was too slow: {o} of {n} gaps went over the app’s {s}-second limit. So restoration does not use it: it now ranks with a Strands Decider fine-tuned for Tamil instead. The tutor uses the general model, to decide whether a learner moves on, repeats or gets a hint.',
  'bench.dec3':
    'The small Sparrow Deciders do not help with restoration: their vocabularies are English and do not cover Tamil written in English letters. Their best run scored a top-1 of {best} on {n} hard test gaps, close to a random pick among the top three ({rnd}); always taking the first proposal scores {first}.',
  'bench.dec4':
    'For tutor decisions, Sparrow nano’s choices agree with the tutor’s rules at a rate of {fin} once the guardrails are applied ({raw} before), on {n} scripted learner states.',

  'bench.methodTitle': 'How this was measured',
  'bench.m1':
    'Splits are by inscription, never by gap: {tr} inscriptions for training, {va} for choosing settings (validation) and {te} for the test ({items} gaps). No inscription is in two splits.',
  'bench.m2':
    'Settings were chosen on {sel} validation gaps by a rule written down before any variant was scored. The test gaps were scored once.',
  'bench.m3': 'Differences use exact McNemar tests on the same gaps; intervals are 95% bootstrap intervals ({b} resamples).',
  'bench.m4': 'Gap lengths are counted in Tamil letters.',
  'bench.m5':
    '“Matches the editors’ restoration” means the fill equals the text a DHARMA editor supplied. That is evidence, not proof: an editor’s restoration is expert judgement, and a different fill is not shown to be wrong.',
  'bench.m6':
    'Texts: DHARMA editions, CC BY-SA 4.0. The benchmark is derived from them, shared under the same licence, and can be downloaded from the repository’s benchmark folder with its data card.',
  'bench.reports': 'The reports',
  'bench.rep.deployed': 'Pre-rank configuration (deployed before the switch), test scored once',
  'bench.rep.preregistration': 'Pre-registered selection rule',
  'bench.rep.test': 'Full test evaluation (PR #31)',
  'bench.rep.val': 'Validation selection',
  'bench.rep.decider': 'Decider benchmark',
  'bench.rep.ocr': 'Photo reader evaluation',
  'bench.rep.data_card': 'Benchmark data card',
  'bench.rep.stats': 'Benchmark counts (stats.json)',

  'bench.runTitle': 'Run it yourself',
  'bench.runLede':
    'Run the built-in benchmark or upload your own gaps as JSONL. A short run is noisy; the numbers above are the reference.',
  'bench.runSignIn': 'Sign in to run it yourself.',
  'how.resultsLink': 'See all the benchmark results',
} as const;

// Every Tamil string below is PENDING a native-speaker check (the convention in strings.ts).
export const taBench: Record<keyof typeof enBench, string> = {
  'bench.kicker': 'முடிவுகள்',
  'bench.title': 'அளவுகோல் முடிவுகள்',
  'bench.lede':
    'இழந்த எழுத்துகளைப் பதிப்பாசிரியர்கள் மீட்டமைத்தபடியே எழுத்து எவ்வளவு அடிக்கடி மீட்டமைக்கிறது என்பது, அது ஒருபோதும் சரிசெய்யப்படாத {ins} கல்வெட்டுகளின் {n} இடைவெளிகளில் அளக்கப்பட்டது. ஒவ்வொரு எண்ணும் அதன் அறிக்கைக்கு இணைப்பு தருகிறது. முதன்மை எண்கள், கூடுதல் பயிற்சி பெற்ற Strands Decider-க்கு மாறுவதற்கு முன் செயலி இயக்கிய முன்வரிசை அமைப்புக்கானவை; இப்போதைய அமைப்பு இன்னும் இவ்வாறு மதிப்பிடப்படவில்லை.',
  'bench.statTop1': 'முதல் முன்மொழிவு பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகிறது',
  'bench.statTop1Sub': '{n} சோதனை இடைவெளிகளில் {k}',
  'bench.statFill': 'அது நிரப்பத் தேர்ந்தெடுக்கும் இடைவெளிகளில் பொருந்துபவை',
  'bench.statFillSub': '{n} நிரப்புகளில் {k}; இடைவெளிகளில் {cov} நிரப்புகிறது',
  'bench.statLong': 'நான்கு அல்லது அதற்கு மேற்பட்ட எழுத்து இடைவெளிகள்',
  'bench.statLongSub': '{n} நீண்ட இடைவெளிகளில் பொருத்தம்: இன்னும் கடினம்',

  'bench.lbTitle': 'சோதனை இடைவெளிகளில் தரவரிசை',
  'bench.lbLede':
    'Top-1: முதல் முன்மொழிவு பதிப்பாசிரியர்களின் மீட்டமைப்புடன் எவ்வளவு அடிக்கடி பொருந்துகிறது. ஒவ்வொரு பட்டையின் மெல்லிய கோடு அதன் 95% இடைவெளி. எல்லாத் தேர்வுகளும் சரிபார்ப்பு இடைவெளிகளில் செய்யப்பட்ட பின், சோதனை இடைவெளிகள் ஒருமுறை மட்டுமே மதிப்பிடப்பட்டன.',
  'bench.subsetFull': 'எல்லா {n} இடைவெளிகளும்',
  'bench.subsetHard': 'கடினமான இடைவெளிகள் ({n})',
  'bench.subsetHardHint':
    'கடினமான இடைவெளிகளுக்கு வேறு பயிற்சிக் கல்வெட்டில் நெருங்கிய இணைப்பகுதி இல்லை; எனவே ஒரு வழக்கமான சொற்றொடரைப் படியெடுப்பது உதவாது.',
  'bench.sys.deployed': 'எழுத்து, முன்வரிசை அமைப்பு',
  'bench.sys.deployedD': 'Sonnet 4.6, கடினமான இடைவெளிகளுக்கு Opus 4.6, எழுத்து 5-gram கொண்டு மறுவரிசைப்படுத்தல்; கூடுதல் பயிற்சி பெற்ற தீர்மானிக்கு முன் செயலி இயக்கியது',
  'bench.sys.ngram': 'எழுத்து 5-gram',
  'bench.sys.ngramD': 'பயிற்சி நூல்களிலிருந்து மட்டுமே எழுத்துகளை ஊகிக்கிறது; AI மாதிரி இல்லை',
  'bench.sys.routed2b': 'உள்ளூர் 2B தீர்மானியுடன் வழிப்படுத்தல்',
  'bench.sys.routed2bD': 'PR #31-இல் அளக்கப்பட்ட, முந்தைய அமைப்பு',
  'bench.sys.copy': 'சிறந்த இணைப்பகுதியைப் படியெடு',
  'bench.sys.copyD': 'வேறு கல்வெட்டின் பொருந்தும் பகுதியைப் படியெடுக்கிறது',
  'bench.sys.sonnet': 'Sonnet 4.6 மட்டும்',
  'bench.sys.sonnetD': 'ஒரே மாதிரி; மேலேற்றமும் 5-gram-உம் இல்லை',
  'bench.colSystem': 'அமைப்பு',
  'bench.colTop1': 'Top-1 [95% இடைவெளி]',
  'bench.colMatches': 'பொருத்தங்கள்',
  'bench.colVs': 'முன்வரிசை அமைப்புடன் ஒப்பீடு',
  'bench.vs': 'முன்வரிசை அமைப்பு மட்டும் {a}, இது மட்டும் {b}; p {p}',
  'bench.vsSelf': 'ஒப்பீட்டு அடிப்படை',
  'bench.vsNone': 'அறிக்கைகளில் சோதிக்கப்படவில்லை',
  'bench.vsNote':
    'p என்பது அதே இடைவெளிகளில் exact McNemar சோதனை; இரண்டில் ஒன்று மட்டும் பொருந்திய இடைவெளிகளை எண்ணுகிறது. 0.05-க்குக் கீழ் என்றால், வேறுபாடு தற்செயலாக இருக்க வாய்ப்புக் குறைவு.',
  'bench.source': 'மூலம்',

  'bench.stopTitle': 'எப்போது நிறுத்துவது என்று அறிதல்',
  'bench.stopBody':
    'ஊகிப்பதற்குப் பதிலாக எழுத்து ஓர் இடைவெளியைத் திறந்து விடலாம். சரிபார்ப்பு இடைவெளிகளில் பொருத்திய நம்பிக்கை வரம்புகளில், அது சோதனை இடைவெளிகளில் {cov} நிரப்புகிறது; அந்த நிரப்புகளில் {acc} பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகின்றன ({n}-இல் {k}). திறந்து விடப்பட்டவை வல்லுநருக்குச் செல்கின்றன.',
  'bench.relTitle': 'அதன் நம்பிக்கை சொல்வதைப் பொருள்படுத்துகிறதா?',
  'bench.relBody':
    'ஒவ்வொரு பட்டையும் {n} சோதனை இடைவெளிகளை எழுத்து தந்த நம்பிக்கையின்படி குழுவாக்குகிறது; அதன் உயரம் அவை எவ்வளவு அடிக்கடி பொருந்தின என்பது. புள்ளிக்கோட்டுக்கு அருகிலுள்ள பட்டைகள், சொன்ன 70% ஏறத்தாழ 70% பொருந்துகிறது என்பதைக் காட்டும்.',
  'bench.ece': 'கோட்டிலிருந்து சராசரித் தொலைவு (ECE): {ece}. குறைவே நல்லது; 0 என்றால் முழுமை.',
  'bench.relChart': 'நம்பிக்கையும் முதல் முன்மொழிவு பொருந்திய அளவும், சோதனை இடைவெளிகள்',
  'bench.relAxis': 'கிடைமட்டம்: நம்பிக்கை (%), செங்குத்து: பொருந்தியவை (%)',

  'bench.gapTitle': 'எங்கே தவறுகிறது: நீண்ட இடைவெளிகள்',
  'bench.gapBody':
    'பெரும்பாலான சோதனை இடைவெளிகள் ஒற்றை எழுத்து; அங்கே அது நன்றாகச் செயல்படுகிறது. நான்கு அல்லது அதற்கு மேற்பட்ட எழுத்துகள் இழந்திருந்தால் {x} மட்டுமே பொருந்துகிறது; இது இணைப்பகுதியைப் படியெடுப்பதற்குச் சமம் ({c}). நீண்ட மீட்டமைப்புகளுக்கு இன்னும் கல்வெட்டியலாளர் தேவை.',
  'bench.colGap': 'இழந்த எழுத்துகள்',
  'bench.colGaps': 'இடைவெளிகள்',
  'bench.gap.1 letter': '1 எழுத்து',
  'bench.gap.2-3 letters': '2 அல்லது 3 எழுத்துகள்',
  'bench.gap.4+ letters': '4 அல்லது அதற்கு மேல்',

  'bench.ocrTitle': 'ஒளிப்படங்களைப் படித்தல்',
  'bench.ocrBody':
    'எழுத்துப் பிழை விகிதம்: வாசிப்பான் தவறாகப் படிக்கும் எழுத்துகளின் பங்கு; குறைவே நல்லது. தமிழ் எழுத்துத் தகடுகள் சோதனைப் பிரிவு வரிகளிலிருந்து, நவீன எழுத்துருவில் கல் அமைப்பின் மேல் வரையப்பட்டவை; உண்மையான பழைய எழுத்து வடிவங்கள் கடினமானவை.',
  'bench.ocr.clean': 'தமிழ் எழுத்து, தெளிவானது ({n} தகடுகள்)',
  'bench.ocr.photo': 'தமிழ் எழுத்து, ஒளிப்படம் போன்றது ({n} தகடுகள்)',
  'bench.ocr.weathered': 'தமிழ் எழுத்து, தேய்ந்தது ({n} தகடுகள்)',
  'bench.ocr.printed': 'அச்சிட்ட தமிழ்ப் பக்கங்கள் ({n} உண்மையான வருடல்கள்)',
  'bench.ocr.brahmi': 'தமிழ்-பிராமி ({n} உண்மையான ஒளிப்படங்கள்)',
  'bench.ocrFail':
    'தமிழ்-பிராமி படிக்கப்படுவதில்லை: ஜம்பை கல்வெட்டின் {n} உண்மையான ஒளிப்படங்களில் பிழை விகிதம் {x}. எழுத்துமுறை தமிழ்-பிராமி, வட்டெழுத்து அல்லது கிரந்தம் போலத் தெரிந்தால் செயலி எச்சரிக்கிறது. வட்டெழுத்து அளக்கப்படவே இல்லை.',
  'bench.ocrChart': 'நிலைமையின்படி ஒளிப்பட வாசிப்பானின் எழுத்துப் பிழை விகிதம்',

  'bench.decTitle': 'Strands Decider: ஒரு நேர்மையான எதிர்மறை முடிவு',
  'bench.dec1':
    'நிரப்பைத் தேர்ந்தெடுக்கும் படியாக hosted Strands Decider (v19)-ஐ முயன்றோம். அதற்காக ஒதுக்கிய {n} சரிபார்ப்பு இடைவெளிகளில், அது {a} பொருந்தியது; அது இல்லாத அமைப்பு {b} ({x}, {y} இடைவெளிகளில் ஒன்று மட்டும் பொருந்தியது, p = {p}): சமநிலை.',
  'bench.dec2':
    'அது மிக மெதுவாக இருந்தது: {n} இடைவெளிகளில் {o} செயலியின் {s} வினாடி வரம்பைத் தாண்டின. எனவே மீட்டமைப்பு அதைப் பயன்படுத்துவதில்லை; இப்போது தமிழுக்காகக் கூடுதல் பயிற்சி பெற்ற Strands Decider-ஐப் பயன்படுத்துகிறது. கற்பவர் முன்செல்வதா, மீண்டும் செய்வதா, குறிப்பு பெறுவதா என்பதைத் தீர்மானிக்க ஆசிரியர் பகுதி பொது மாதிரியைப் பயன்படுத்துகிறது.',
  'bench.dec3':
    'சிறிய Sparrow Decider-கள் மீட்டமைப்புக்கு உதவுவதில்லை: அவற்றின் சொற்களஞ்சியம் ஆங்கிலம்; ஆங்கில எழுத்துகளில் எழுதிய தமிழை அவை அறியா. அவற்றின் சிறந்த ஓட்டம் {n} கடினமான இடைவெளிகளில் {best} பொருந்தியது; இது முதல் மூன்றில் தற்செயலாக ஒன்றைத் தேர்வதற்கு அருகில் ({rnd}); எப்போதும் முதல் முன்மொழிவை எடுத்தால் {first}.',
  'bench.dec4':
    'ஆசிரியர் முடிவுகளில், பாதுகாப்பு விதிகள் சேர்த்த பின் Sparrow nano ஆசிரியரின் விதிகளுடன் {fin} ஒத்துப்போகிறது (அதற்கு முன் {raw}); {n} எழுதப்பட்ட கற்பவர் நிலைகளில்.',

  'bench.methodTitle': 'இது எப்படி அளக்கப்பட்டது',
  'bench.m1':
    'பிரிவுகள் கல்வெட்டு வாரியாக, இடைவெளி வாரியாக அல்ல: பயிற்சிக்கு {tr} கல்வெட்டுகள், அமைப்புகளைத் தேர்ந்தெடுக்க (சரிபார்ப்பு) {va}, சோதனைக்கு {te} ({items} இடைவெளிகள்). எந்தக் கல்வெட்டும் இரண்டு பிரிவுகளில் இல்லை.',
  'bench.m2':
    'எந்த மாற்றும் மதிப்பிடப்படும் முன்பே எழுதி வைத்த விதிப்படி, {sel} சரிபார்ப்பு இடைவெளிகளில் அமைப்புகள் தேர்ந்தெடுக்கப்பட்டன. சோதனை இடைவெளிகள் ஒருமுறை மட்டுமே மதிப்பிடப்பட்டன.',
  'bench.m3': 'வேறுபாடுகளுக்கு அதே இடைவெளிகளில் exact McNemar சோதனை; இடைவெளிகள் 95% bootstrap இடைவெளிகள் ({b} மறுமாதிரிகள்).',
  'bench.m4': 'இடைவெளி நீளம் தமிழ் எழுத்துகளில் எண்ணப்படுகிறது.',
  'bench.m5':
    '“பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகிறது” என்றால், நிரப்பு ஒரு DHARMA பதிப்பாசிரியர் தந்த உரைக்குச் சமம். இது சான்று, நிரூபணம் அல்ல: பதிப்பாசிரியரின் மீட்டமைப்பு வல்லுநர் மதிப்பீடு; வேறுபட்ட நிரப்பு தவறு என்று காட்டப்படவில்லை.',
  'bench.m6':
    'உரைகள்: DHARMA பதிப்புகள், CC BY-SA 4.0. அளவுகோல் அவற்றிலிருந்து பெறப்பட்டது, அதே உரிமத்தில் பகிரப்படுகிறது; களஞ்சியத்தின் benchmark கோப்புறையிலிருந்து அதன் தரவு அட்டையுடன் பதிவிறக்கலாம்.',
  'bench.reports': 'அறிக்கைகள்',
  'bench.rep.deployed': 'முன்வரிசை அமைப்பு (மாற்றத்துக்கு முன் செயல்பாட்டில்), சோதனை ஒருமுறை மதிப்பீடு',
  'bench.rep.preregistration': 'முன்பதிவு செய்த தேர்வு விதி',
  'bench.rep.test': 'முழுச் சோதனை மதிப்பீடு (PR #31)',
  'bench.rep.val': 'சரிபார்ப்புத் தேர்வு',
  'bench.rep.decider': 'தீர்மானி அளவுகோல்',
  'bench.rep.ocr': 'ஒளிப்பட வாசிப்பான் மதிப்பீடு',
  'bench.rep.data_card': 'அளவுகோல் தரவு அட்டை',
  'bench.rep.stats': 'அளவுகோல் எண்ணிக்கைகள் (stats.json)',

  'bench.runTitle': 'நீங்களே இயக்குங்கள்',
  'bench.runLede':
    'உள்ளமைந்த அளவுகோலை இயக்குங்கள் அல்லது உங்கள் இடைவெளிகளை JSONL ஆகப் பதிவேற்றுங்கள். சிறிய ஓட்டம் நிலையற்றது; மேலே உள்ள எண்களே அடிப்படை.',
  'bench.runSignIn': 'நீங்களே இயக்க உள்நுழையுங்கள்.',
  'how.resultsLink': 'எல்லா அளவுகோல் முடிவுகளையும் பாருங்கள்',
};
