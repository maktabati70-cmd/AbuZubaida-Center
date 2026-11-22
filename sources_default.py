# -*- coding: utf-8 -*-
"""
مركز أبو زبيدة للتتبع والرصد — المصادر الافتراضية.
هنا قوائم الخلاصات وقنوات تيليغرام وحسابات Bluesky ووسوم المواضيع.
عند إضافة مصدر جديد ارفع رقم SOURCES_VERSION حتى يُضاف عند المستخدمين دون حذف تعديلاتهم.
"""

def F(name_ar, cat, url, site="", lang="en", query=""):
    d = {"name_ar": name_ar, "cat": cat, "url": url, "site": site, "lang": lang}
    if query:
        d["query"] = query       # مصدر بحث: يجمع الأخبار من أخبار Google بهذه الكلمات
    return d


DEFAULT_FEEDS = [
    # ── الأخبار العالمية
    F("بي بي سي - العالم", "world", "https://feeds.bbci.co.uk/news/world/rss.xml", "bbc.com"),
    F("الجزيرة الإنجليزية", "world", "https://www.aljazeera.com/xml/rss/all.xml", "aljazeera.com"),
    F("الغارديان", "world", "https://www.theguardian.com/world/rss", "theguardian.com"),
    F("نيويورك تايمز", "world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "nytimes.com"),
    F("دويتشه فيله", "world", "https://rss.dw.com/rdf/rss-en-world", "dw.com"),
    F("فرانس 24", "world", "https://www.france24.com/en/rss", "france24.com"),
    F("إن بي آر", "world", "https://feeds.npr.org/1004/rss.xml", "npr.org"),
    F("رويترز", "world", "", "reuters.com"),
    F("أسوشيتد برس", "world", "", "apnews.com"),
    F("ميدل إيست آي", "world", "https://www.middleeasteye.net/rss", "middleeasteye.net"),
    F("بوليتيكو أوروبا", "world", "https://www.politico.eu/feed/", "politico.eu"),
    # ── الأخبار العربية
    F("الجزيرة نت", "arab", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9", "aljazeera.net", "ar"),
    F("بي بي سي عربي", "arab", "https://feeds.bbci.co.uk/arabic/rss.xml", "bbc.com", "ar"),
    F("فرانس 24 عربي", "arab", "https://www.france24.com/ar/rss", "france24.com", "ar"),
    F("دويتشه فيله عربي", "arab", "https://rss.dw.com/rdf/rss-ar-all", "dw.com", "ar"),
    F("العربية", "arab", "https://www.alarabiya.net/feed/rss2/ar.xml", "alarabiya.net", "ar"),
    F("سكاي نيوز عربية", "arab", "", "skynewsarabia.com", "ar"),
    F("الشرق الأوسط", "arab", "https://aawsat.com/feed", "aawsat.com", "ar"),
    F("إندبندنت عربية", "arab", "", "independentarabia.com", "ar"),
    F("العربي الجديد", "arab", "", "alaraby.co.uk", "ar"),
    F("عنب بلدي", "arab", "https://www.enabbaladi.net/feed", "enabbaladi.net", "ar"),
    F("روسيا اليوم عربي", "arab", "https://arabic.rt.com/rss/", "arabic.rt.com", "ar"),
    # ── مراكز الأبحاث الأجنبية
    F("معهد بروكينغز", "think_global", "https://www.brookings.edu/feed/", "brookings.edu"),
    F("مركز الدراسات الاستراتيجية والدولية CSIS", "think_global", "", "csis.org"),
    F("مؤسسة راند", "think_global", "", "rand.org"),
    F("مؤسسة كارنيغي", "think_global", "", "carnegieendowment.org"),
    F("تشاتام هاوس", "think_global", "", "chathamhouse.org"),
    F("مجلس العلاقات الخارجية CFR", "think_global", "", "cfr.org"),
    F("المجلس الأطلسي", "think_global", "https://www.atlanticcouncil.org/feed/", "atlanticcouncil.org"),
    F("مجموعة الأزمات الدولية", "think_global", "", "crisisgroup.org"),
    F("معهد واشنطن", "think_global", "", "washingtoninstitute.org"),
    F("فورين بوليسي", "think_global", "https://foreignpolicy.com/feed/", "foreignpolicy.com"),
    F("فورين أفيرز", "think_global", "https://www.foreignaffairs.com/rss.xml", "foreignaffairs.com"),
    F("معهد الشرق الأوسط MEI", "think_global", "", "mei.edu"),
    F("المجلس الأوروبي للعلاقات الخارجية", "think_global", "https://ecfr.eu/feed/", "ecfr.eu"),
    F("المعهد الدولي للدراسات الاستراتيجية IISS", "think_global", "", "iiss.org"),
    F("مركز ويلسون", "think_global", "", "wilsoncenter.org"),
    F("مركز ستيمسون", "think_global", "https://www.stimson.org/feed/", "stimson.org"),
    # ── مراكز الأبحاث العربية
    F("مركز الجزيرة للدراسات", "think_arab", "", "studies.aljazeera.net", "ar"),
    F("مركز مالكوم كير–كارنيغي", "think_arab", "", "carnegieendowment.org/middle-east", "ar"),
    F("المركز العربي للأبحاث ودراسة السياسات", "think_arab", "", "dohainstitute.org", "ar"),
    F("مركز حرمون للدراسات المعاصرة", "think_arab", "https://www.harmoon.org/feed/", "harmoon.org", "ar"),
    F("مركز جسور للدراسات", "think_arab", "https://www.jusoor.co/feed/", "jusoor.co", "ar"),
    F("مركز عمران للدراسات الاستراتيجية", "think_arab", "https://www.omrandirasat.org/feed/", "omrandirasat.org", "ar"),
    F("مركز الإمارات للسياسات", "think_arab", "", "epc.ae", "ar"),
    F("مركز الأهرام للدراسات السياسية", "think_arab", "", "acpss.ahram.org.eg", "ar"),
    F("مركز المستقبل للأبحاث", "think_arab", "", "futureuae.com", "ar"),
    F("المعهد الدولي للدراسات الإيرانية رصانة", "think_arab", "", "rasanah-iiis.org", "ar"),
    F("مركز دراسات الوحدة العربية", "think_arab", "", "caus.org.lb", "ar"),
    F("المعهد المصري للدراسات", "think_arab", "https://eipss-eg.org/feed/", "eipss-eg.org", "ar"),
    # ── مكافحة الإرهاب والتطرف
    F("مركز مكافحة الإرهاب - ويست بوينت", "terror", "https://ctc.westpoint.edu/feed/", "ctc.westpoint.edu"),
    F("المركز الدولي لمكافحة الإرهاب ICCT", "terror", "", "icct.nl"),
    F("لونغ وور جورنال", "terror", "https://www.longwarjournal.org/feed", "longwarjournal.org"),
    F("الشبكة العالمية للتطرف والتكنولوجيا GNET", "terror", "https://gnet-research.org/feed/", "gnet-research.org"),
    F("مؤسسة جيمستاون", "terror", "https://jamestown.org/feed/", "jamestown.org"),
    F("مشروع مكافحة التطرف CEP", "terror", "", "counterextremism.com"),
    F("برنامج التطرف - جامعة جورج واشنطن", "terror", "", "extremism.gwu.edu"),
    F("معهد الحوار الاستراتيجي ISD", "terror", "", "isdglobal.org"),
    F("لوفير", "terror", "", "lawfaremedia.org"),
    F("مرصد الأزهر لمكافحة التطرف", "terror", "", "azhar.eg", "ar"),
    F("المركز الأوروبي لدراسات مكافحة الإرهاب", "terror", "https://www.europarabct.com/feed/", "europarabct.com", "ar"),
    # ── الحروب والنزاعات والدفاع
    F("معهد دراسة الحرب ISW", "war", "", "understandingwar.org"),
    F("وور أون ذا روكس", "war", "https://warontherocks.com/feed/", "warontherocks.com"),
    F("ديفنس ون", "war", "https://www.defenseone.com/rss/all/", "defenseone.com"),
    F("بريكينغ ديفنس", "war", "https://breakingdefense.com/feed/", "breakingdefense.com"),
    F("ذا وور زون", "war", "https://www.twz.com/feed", "twz.com"),
    F("ديفنس نيوز", "war", "", "defensenews.com"),
    F("بيلينغكات", "war", "https://www.bellingcat.com/feed/", "bellingcat.com"),
    F("أكليد لبيانات النزاعات", "war", "", "acleddata.com"),
    F("كييف إندبندنت", "war", "https://kyivindependent.com/rss/", "kyivindependent.com"),
    F("سمول وورز جورنال", "war", "", "smallwarsjournal.com"),
    F("جينز", "war", "", "janes.com"),
    F("إيروورز", "war", "", "airwars.org"),
]

DEFAULT_FEEDS += [
    # ── الأخبار الاقتصادية
    F("بي بي سي - اقتصاد", "economy", "https://feeds.bbci.co.uk/news/business/rss.xml", "bbc.com"),
    F("الغارديان - اقتصاد", "economy", "https://www.theguardian.com/business/rss", "theguardian.com"),
    F("سي إن بي سي", "economy", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cnbc.com"),
    F("ماركت ووتش", "economy", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "marketwatch.com"),
    F("الإيكونوميست - مال واقتصاد", "economy", "https://www.economist.com/finance-and-economics/rss.xml", "economist.com"),
    F("فايننشال تايمز", "economy", "", "ft.com"),
    F("بلومبرغ", "economy", "", "bloomberg.com"),
    F("أويل برايس", "economy", "https://oilprice.com/rss/main", "oilprice.com"),
    F("اقتصاد الشرق مع بلومبرغ", "economy", "", "asharqbusiness.com", "ar"),
    F("سي إن بي سي عربية", "economy", "", "cnbcarabia.com", "ar"),
    F("صحيفة الاقتصادية", "economy", "", "aleqt.com", "ar"),
    F("أرقام", "economy", "", "argaam.com", "ar"),
    F("العربي الجديد - اقتصاد", "economy", "", "alaraby.co.uk/economy", "ar"),
]
DEFAULT_FEEDS += [
    # ── إضافات منتقاة: مكافحة الإرهاب والتطرف
    F("المركز الوطني لدراسة الإرهاب START (أمريكا)", "terror", "", "start.umd.edu"),
    F("مركز صوفان (أمريكا)", "terror", "https://thesoufancenter.org/feed/", "thesoufancenter.org"),
    F("المركز الدولي لدراسة التطرف ICSR (بريطانيا)", "terror", "https://icsr.info/feed/", "icsr.info"),
    F("مركز أبحاث التطرف C-REX (النرويج)", "terror", "", "sv.uio.no/c-rex"),
    F("مركز أبحاث وأدلة التهديدات الأمنية CREST (بريطانيا)", "terror", "", "crestresearch.ac.uk"),
    # ── إضافات منتقاة: مراكز أجنبية
    F("مؤسسة الدفاع عن الديمقراطيات FDD (أمريكا)", "think_global", "", "fdd.org"),
    F("مركز بلفر - هارفارد (أمريكا)", "think_global", "", "belfercenter.org"),
    F("المعهد الفرنسي للعلاقات الدولية IFRI (فرنسا)", "think_global", "", "ifri.org"),
    F("مؤسسة الأبحاث الاستراتيجية FRS (فرنسا)", "think_global", "", "frstrategie.org"),
    F("معهد الاتحاد الأوروبي للدراسات الأمنية EUISS", "think_global", "", "iss.europa.eu"),
    F("معهد كلينغينديل (هولندا)", "think_global", "", "clingendael.org"),
    F("مركز الدراسات الأمنية CSS - زيورخ (سويسرا)", "think_global", "", "css.ethz.ch"),
    F("المعهد الملكي إلكانو (إسبانيا)", "think_global", "", "realinstitutoelcano.org"),
    F("المعهد النرويجي للشؤون الدولية NUPI", "think_global", "", "nupi.no"),
    F("المعهد الأسترالي للسياسات الاستراتيجية ASPI", "think_global", "https://www.aspistrategist.org.au/feed/", "aspistrategist.org.au"),
    F("المجلس الروسي للشؤون الدولية RIAC (روسيا)", "think_global", "", "russiancouncil.ru"),
    F("نادي فالداي للحوار (روسيا)", "think_global", "", "valdaiclub.com"),
    # ── إضافات منتقاة: الحروب والأمن
    F("المعهد الملكي للخدمات المتحدة RUSI (بريطانيا)", "war", "", "rusi.org"),
    F("معهد ستوكهولم لأبحاث السلام SIPRI", "war", "", "sipri.org"),
    F("معهد أبحاث السلام في أوسلو PRIO", "war", "", "prio.org"),
    F("مركز التقييمات الاستراتيجية والميزانية CSBA (أمريكا)", "war", "", "csbaonline.org"),
    F("معهد الدراسات الأمنية ISS Africa", "war", "", "issafrica.org"),
    F("المركز الأفريقي للدراسات الاستراتيجية", "war", "https://africacenter.org/feed/", "africacenter.org"),
    F("المركز الأفريقي لحل النزاعات ACCORD", "war", "https://www.accord.org.za/feed/", "accord.org.za"),
    # ── إضافات منتقاة: مراكز عربية وشرق أوسطية
    F("المجلس المصري للشؤون الخارجية (مصر)", "think_arab", "", "ecfa-eg.org", "ar"),
    F("مركز الإمارات للدراسات والبحوث الاستراتيجية (الإمارات)", "think_arab", "", "ecssr.ae", "ar"),
    F("مركز الملك فيصل للبحوث والدراسات الإسلامية (السعودية)", "think_arab", "", "kfcris.com", "ar"),
    F("مركز الخليج للأبحاث (السعودية)", "think_arab", "", "grc.net", "ar"),
    F("مركز البحرين للدراسات الاستراتيجية دراسات (البحرين)", "think_arab", "", "derasat.org.bh", "ar"),
    F("مركز القدس للدراسات السياسية (الأردن)", "think_arab", "", "alqudscenter.org", "ar"),
    F("مركز الرافدين للحوار (العراق)", "think_arab", "", "alrafidaincenter.com", "ar"),
    F("معهد الشرق الأوسط للبحوث MERI (العراق)", "think_arab", "", "meri-k.org"),
]
DEFAULT_FEEDS += [
    # ── الأمن والاستخبارات: منصات تحليل ودراسات
    F("جاست سكيوريتي", "intel", "https://www.justsecurity.org/feed/", "justsecurity.org"),
    F("ذا سايفر بريف", "intel", "", "thecipherbrief.com"),
    F("سباي توك", "intel", "https://www.spytalk.co/feed", "spytalk.co"),
    F("إنتليجنس أونلاين", "intel", "", "intelligenceonline.com"),
    F("غراي داينامكس للتحليل الاستخباراتي", "intel", "https://greydynamics.com/feed/", "greydynamics.com"),
    F("ذا ريكورد (استخبارات التهديدات)", "intel", "https://therecord.media/feed/", "therecord.media"),
    F("سايبر سكوب", "intel", "https://cyberscoop.com/feed/", "cyberscoop.com"),
    F("مشروع الاستخبارات - مركز بلفر", "intel", "", "", "en", query='site:belfercenter.org intelligence'),
    F("مجلة الاستخبارات والأمن القومي", "intel", "https://www.tandfonline.com/feed/rss/rint20", "tandfonline.com"),
    # ── الأمن والاستخبارات: رصد الأخبار
    F("رصد: أخبار الاستخبارات والتجسس", "intel", "", "", "en",
      query='"intelligence agency" OR espionage OR "spy ring" OR counterintelligence'),
    F("رصد: الاستخبارات بالعربية", "intel", "", "", "ar", query="استخبارات OR تجسس OR المخابرات"),
    F("رصد: الأمن السيبراني والهجمات المدعومة من دول", "intel", "", "", "en",
      query='"state-sponsored" hackers OR cyberattack OR "cyber espionage"'),
    F("رصد: الأمن القومي", "intel", "", "", "en", query='"national security" OR "security services" OR "terror plot"'),
]
def YT(name_ar, cat, channel_id, lang="en"):
    return F(name_ar, cat, f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", "", lang)


DEFAULT_FEEDS += [
    # ── قنوات يوتيوب الإخبارية (روابط RSS مجانية)
    YT("يوتيوب: الجزيرة", "arab", "UCfiwzLy-8yKzIbsmZTzxDgw", "ar"),
    YT("يوتيوب: العربية", "arab", "UCahpxixMCwoANAftn6IxkTg", "ar"),
    YT("يوتيوب: سكاي نيوز عربية", "arab", "UCIJXOvggjKtCagMfxvcCzAA", "ar"),
    YT("يوتيوب: بي بي سي عربي", "arab", "UCelk6aHijZq-GJBBB9YpReA", "ar"),
    YT("يوتيوب: الجزيرة الإنجليزية", "world", "UCNye-wNBqNL5ZzHSJj3l8Bg"),
    YT("يوتيوب: رويترز", "world", "UChqUTb7kYRX8-EiaN3XFrSQ"),
    YT("يوتيوب: دويتشه فيله", "world", "UCknLrEdhRCp1aegoMqRaCZg"),
    YT("يوتيوب: فرانس 24", "world", "UCQfwfsi5VrQ8yKZ-UWmAEFg"),
]
# حسابات Bluesky (بديل X المجاني: واجهته عامة بلا مفتاح). أضف أو احذف من الصفحة مباشرة.
DEFAULT_BSKY = [
    {"handle": "apnews.com", "name_ar": "أسوشيتد برس"},
    {"handle": "reuters.com", "name_ar": "رويترز"},
    {"handle": "nytimes.com", "name_ar": "نيويورك تايمز"},
    {"handle": "washingtonpost.com", "name_ar": "واشنطن بوست"},
    {"handle": "theguardian.com", "name_ar": "الغارديان"},
    {"handle": "economist.com", "name_ar": "الإيكونوميست"},
    {"handle": "bellingcat.com", "name_ar": "بيلينغكات"},
    {"handle": "kyivindependent.com", "name_ar": "كييف إندبندنت"},
]
DEFAULT_FEEDS += [
    # ── البيانات الرسمية: وزارات وقيادات عسكرية ومنظمات دولية (المصدر الأول قبل الصحف)
    F("وزارة الدفاع الأمريكية: بيانات", "official",
      "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=9&Site=945&max=15", "defense.gov"),
    F("القيادة المركزية الأمريكية CENTCOM", "official", "", "centcom.mil"),
    F("وزارة الخارجية الأمريكية: بيانات صحفية", "official", "https://www.state.gov/rss-feed/press-releases/feed/", "state.gov"),
    F("وزارة العدل الأمريكية: قضايا الأمن القومي", "official", "https://www.justice.gov/feeds/opa/justice-news.xml", "justice.gov"),
    F("وزارة الخزانة الأمريكية: العقوبات", "official", "", "home.treasury.gov"),
    F("أخبار الأمم المتحدة: الشرق الأوسط", "official",
      "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml", "news.un.org"),
    F("مجلس الأمن الدولي: بيانات صحفية", "official", "", "press.un.org"),
    F("حلف الناتو: أخبار", "official", "https://www.nato.int/cps/rss/en/natohq/rssFeed.xsl/rssFeed.xml", "nato.int"),
    F("الخارجية البريطانية", "official",
      "https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom", "gov.uk"),
    F("الاتحاد الأوروبي: الخدمة الخارجية", "official", "", "eeas.europa.eu"),
    F("أخبار الأمم المتحدة بالعربية", "official", "https://news.un.org/feed/subscribe/ar/news/all/rss.xml", "news.un.org", "ar"),
    F("وزارة الدفاع التركية", "official", "", "msb.gov.tr", "tr"),
]
DEFAULT_FEEDS += [
    # ── مراكز ومنصات متخصصة في الإرهاب والجماعات الإسلامية
    F("جهادولوجي: أرشيف إصدارات الجماعات (هارون زيلين)", "terror", "https://jihadology.net/feed/", "jihadology.net"),
    F("ميليتانت واير: رصد الجماعات المسلحة", "terror", "https://www.militantwire.com/feed", "militantwire.com"),
    F("كريتيكال ثريتس: مشروع التهديدات الحرجة", "terror", "", "criticalthreats.org"),
    F("مجموعة سايت للاستخبارات SITE", "terror", "", "siteintelgroup.com"),
    F("ميمري: مراقبة التهديد الجهادي JTTM", "terror", "", "memri.org"),
    F("التقنية ضد الإرهاب", "terror", "", "techagainstterrorism.org"),
    F("فوكس بول: شبكة أبحاث التطرف العنيف", "terror", "https://voxpol.eu/feed/", "voxpol.eu"),
    F("كونسورتيوم أبحاث الإرهاب TRAC", "terror", "", "trackingterrorism.org"),
    F("منتدى الشرق الأوسط: رصد الإسلاموية", "terror", "", "meforum.org"),
    F("عين أوروبية على التطرف", "terror", "", "eeradicalization.com", "ar"),
    F("مركز المسبار للدراسات والبحوث", "terror", "https://www.almesbar.net/feed/", "almesbar.net", "ar"),
    F("حفريات: الجماعات والتيارات الإسلامية", "terror", "", "hafryat.com", "ar"),
    F("تريندز للبحوث والاستشارات", "terror", "", "trendsresearch.org", "ar"),
    F("مرصد الفتاوى التكفيرية - دار الإفتاء المصرية", "terror", "", "dar-alifta.org", "ar"),
    # ── رصد أخبار الجماعات
    F("رصد: أخبار الجماعات الجهادية", "terror", "", "", "ar",
      query='داعش OR "تنظيم الدولة" OR القاعدة OR "هيئة تحرير الشام" OR "حركة الشباب" OR "بوكو حرام"'),
    F("رصد: Jihadist groups news", "terror", "", "", "en",
      query='"Islamic State" OR al-Qaeda OR al-Shabaab OR JNIM OR ISWAP OR "ISIS-K" OR "Hayat Tahrir"'),
    F("رصد: عمليات مكافحة الإرهاب", "terror", "", "", "en",
      query='counterterrorism operation OR "terror cell" OR "jihadist arrested" OR "ISIS cell"'),
]
DEFAULT_FEEDS += [
    # ── مراكز من القائمة المعتمدة لم تكن مضافة
    F("مركز مكافحة الإرهاب والجريمة العابرة والفساد TraCCC", "terror", "", "traccc.gmu.edu"),
    F("وكالة أبحاث الدفاع السويدية FOI", "think_global", "", "foi.se"),
    F("المعهد الدنماركي للدراسات الدولية DIIS", "think_global", "", "diis.dk"),
    F("المعهد الفنلندي للشؤون الدولية FIIA", "think_global", "", "fiia.fi"),
    F("مركز جنيف للسياسات الأمنية GCSP", "think_global", "", "gcsp.ch"),
    F("المعهد البولندي للشؤون الدولية PISM", "think_global", "", "pism.pl"),
    F("غلوبسيك GLOBSEC", "think_global", "", "globsec.org"),
    F("المعهد التونسي للدراسات الاستراتيجية", "think_arab", "", "ites.tn", "ar"),
    F("الجمعية الفلسطينية لدراسة الشؤون الدولية PASSIA", "think_arab", "", "passia.org"),
    F("المركز الأفريقي لدراسة وأبحاث الإرهاب ACSRT", "terror", "", "", "en",
      query='ACSRT OR CAERT OR "African Centre for the Study and Research on Terrorism"'),
    F("معهد دراسات السلام والأمن IPSS (إثيوبيا)", "think_global", "", "ipss-addis.org"),
    F("مركز الديمقراطية والتنمية CDD (نيجيريا)", "think_global", "", "cddwestafrica.org"),
    F("شبكة غرب أفريقيا لبناء السلام WANEP", "think_global", "", "wanep.org"),
    F("المعهد الجنوب أفريقي للشؤون الدولية SAIIA", "think_global", "", "saiia.org.za"),
    F("كلية الأمن القومي - الجامعة الأسترالية الوطنية", "think_global", "", "nsc.anu.edu.au"),
    F("المعهد الأسترالي للشؤون الدولية", "think_global", "", "internationalaffairs.org.au"),
    F("معهد الاقتصاد العالمي والعلاقات الدولية IMEMO", "think_global", "", "imemo.ru"),
    F("المعهد الروسي للدراسات الاستراتيجية RISS", "think_global", "", "riss.ru"),
    F("مركز PIR للدراسات السياسية", "think_global", "", "pircenter.org"),
    F("معهد الدراسات الشرقية - الأكاديمية الروسية", "think_global", "", "ivran.ru"),
]
SOURCES_VERSION = 10

# قنوات تيليغرام العامة (تعمل مجاناً بلا مفتاح). أضف أو احذف من الصفحة مباشرة.
DEFAULT_TG_CHANNELS = [
    {"channel": "arabicpost_me", "name_ar": "عربي بوست"},
    {"channel": "AJArabic", "name_ar": "الجزيرة"},
    {"channel": "alarabiya", "name_ar": "العربية"},
    {"channel": "skynewsarabia", "name_ar": "سكاي نيوز عربية"},
    {"channel": "bbcarabic", "name_ar": "بي بي سي عربي"},
    {"channel": "EnabBaladi", "name_ar": "عنب بلدي"},
    {"channel": "insiderpaper", "name_ar": "إنسايدر بيبر"},
    {"channel": "QudsNen", "name_ar": "شبكة قدس الإخبارية"},
    {"channel": "ClashReport", "name_ar": "كلاش ريبورت"},
    {"channel": "nanafrica", "name_ar": "أخبار شمال أفريقيا"},
    {"channel": "thejerusalempost", "name_ar": "جيروزاليم بوست"},
    {"channel": "Middle_East_Spectator", "name_ar": "مراقب الشرق الأوسط"},
    {"channel": "AJENews", "name_ar": "الجزيرة الإنجليزية"},
    {"channel": "asharqnews", "name_ar": "الشرق للأخبار"},
    {"channel": "AlHadath", "name_ar": "الحدث"},
    {"channel": "rtarabic", "name_ar": "آر تي عربي"},
    {"channel": "france24_ar", "name_ar": "فرانس 24 عربي"},
    {"channel": "Alaraby_Aljadeed", "name_ar": "العربي الجديد"},
    {"channel": "SyriaTV", "name_ar": "تلفزيون سوريا"},
    {"channel": "rudawarabic", "name_ar": "روداو عربية"},
    {"channel": "kurdistan24arabic", "name_ar": "كردستان 24 عربي"},
    {"channel": "BNONews", "name_ar": "بي إن أو نيوز"},
    {"channel": "WarMonitors", "name_ar": "وور مونيتورز"},
    {"channel": "OSINTdefender", "name_ar": "أوسينت ديفندر"},
]

DEFAULT_X_ACCOUNTS = [
    {"handle": "Reuters", "name_ar": "رويترز"},
    {"handle": "AP", "name_ar": "أسوشيتد برس"},
    {"handle": "BBCBreaking", "name_ar": "بي بي سي عاجل"},
    {"handle": "AJEnglish", "name_ar": "الجزيرة الإنجليزية"},
    {"handle": "AJArabic", "name_ar": "الجزيرة"},
    {"handle": "AlArabiya", "name_ar": "العربية"},
    {"handle": "skynewsarabia", "name_ar": "سكاي نيوز عربية"},
    {"handle": "TheStudyofWar", "name_ar": "معهد دراسة الحرب"},
    {"handle": "CTCWestPoint", "name_ar": "مركز مكافحة الإرهاب - ويست بوينت"},
    {"handle": "LongWarJournal", "name_ar": "لونغ وور جورنال"},
    {"handle": "bellingcat", "name_ar": "بيلينغكات"},
    {"handle": "CrisisGroup", "name_ar": "مجموعة الأزمات الدولية"},
    {"handle": "NATO", "name_ar": "حلف الناتو"},
    {"handle": "CENTCOM", "name_ar": "القيادة المركزية الأمريكية"},
    {"handle": "UN", "name_ar": "الأمم المتحدة"},
    {"handle": "KyivIndependent", "name_ar": "كييف إندبندنت"},
]

TOPIC_TAGS = {
    "داعش": ["داعش", "تنظيم الدولة", "isis", "isil", "islamic state"],
    "القاعدة": ["القاعدة", "al-qaeda", "al qaeda", "alqaeda", "aqap", "jnim"],
    "الإرهاب والتطرف": ["terror", "إرهاب", "extremis", "تطرف", "jihad"],
    "سوريا": ["سوريا", "سورية", "السوري", "دمشق", "syria", "damascus"],
    "غزة وفلسطين": ["غزة", "فلسطين", "الضفة", "gaza", "palestin", "west bank"],
    "أوكرانيا وروسيا": ["ukrain", "أوكران", "russia", "روسيا", "الروسي", "kremlin", "الكرملين"],
    "إيران": ["iran", "إيران", "الإيراني", "tehran", "طهران"],
    "اليمن": ["yemen", "houthi", "اليمن", "الحوثي"],
    "العراق": ["iraq", "العراق", "بغداد", "baghdad"],
    "لبنان": ["lebanon", "لبنان", "hezbollah", "حزب الله"],
    "السودان": ["sudan", "السودان", "الدعم السريع"],
    "ليبيا": ["libya", "ليبيا"],
    "تركيا": ["turkey", "türkiye", "turkiye", "تركيا", "أنقرة", "ankara"],
    "الساحل الإفريقي": ["sahel", "الساحل الإفريقي", "mali", "مالي", "niger", "النيجر", "burkina"],
    "الصين وتايوان": ["china", "الصين", "taiwan", "تايوان", "beijing", "بكين"],
    "المسيّرات": ["drone", "مسيّر", "مسيرة", "مسيرات", "uav"],
    "النووي": ["nuclear", "نووي"],
    "الصواريخ": ["missile", "صاروخ", "صواريخ"],
    "الاستخبارات": ["intelligence", "استخبار", "espionage", "تجسس", "spy", "mossad", "الموساد", "cia", "mi6", "fsb", "المخابرات"],
    "الأمن السيبراني": ["cyber", "سيبران", "hacker", "قراصنة", "ransomware", "اختراق"],
    "النفط والطاقة": ["oil price", "crude", "opec", "النفط", "أوبك", "الغاز الطبيعي", "lng"],
    "الفائدة والتضخم": ["interest rate", "inflation", "federal reserve", "الفائدة", "التضخم", "الفيدرالي"],
    "الذهب والعملات": ["gold price", "الذهب", "dollar", "الدولار", "الليرة", "lira", "currency"],
}
