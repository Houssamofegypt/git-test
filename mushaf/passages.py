"""Passages proposed for the muṣḥaf viewer. Notes may use <i> and <b> only."""

# (surah, first, last, heart verse, English title, Arabic title, note paragraphs)
PASSAGES = [
 (2, 183, 186, 186, "I am near", "فَإِنِّي قَرِيبٌ", [
  "Eighteen times in the Qur'an someone asks the Prophet a question, and fifteen times the answer comes back through him with <i>qul</i>, \u201csay\u201d. I checked every one of them in the database. Here the intermediary is dropped: God answers in the first person, <i>fa-innī qarīb</i>, \u201cthen I am near.\u201d",
  "The other two questions without <i>qul</i> are 4:153, which is answered with a story about Moses, and 79:42, about the Hour, where no answer is given at all. For your question about how God presents Himself, this is the most direct self-presentation in the book.",
  "Context: it sits inside the fasting passage, immediately after “Allah wants ease for you, and does not want hardship for you” (185).",
 ]),
 (13, 19, 24, 24, "For that you were patient", "سَلَٰمٌ عَلَيۡكُم بِمَا صَبَرۡتُمۡ", [
  "This answers the query you gave as an example earlier: paradise promised to those who are patient. The reward is described socially. You enter with the righteous among your parents, spouses and children, and the angels come in from every gate with a greeting that states the reason: <i>salāmun ʿalaykum bimā ṣabartum</i>.",
  "The phrase <i>ʿuqbā al-dār</i>, “the final home”, appears in both verse 22 and verse 24, so the reward bookends the description of the patient. The passage opens by addressing <i>ulū al-albāb</i>, people of understanding.",
 ]),
 (28, 70, 73, 73, "Out of His mercy, night and day", "وَمِن رَّحۡمَتِهِۦ", [
  "This one was picked by the data. I scanned all 6,236 verses for the densest window that holds both night (root ل ي ل) and day (root ن ه ر), and it came out on top.",
  "It is a thought experiment: what if the night never ended, and what if the day never ended? The conclusion names the alternation itself as mercy. The night verse ends with “will you not <b>hear</b>?” and the day verse ends with “will you not <b>see</b>?”, so each one appeals to the sense that works in it. It comes from a surah that opens with the letters Ṭā Sīn Mīm.",
 ]),
 (39, 53, 56, 53, "Do not despair of God's mercy", "لَا تَقۡنَطُواْ مِن رَّحۡمَةِ ٱللَّهِ", [
  "Often called the most hopeful verse in the Qur'an. God calls the transgressors <i>ʿibādī</i>, “My servants”, and claims them as His even as they are named for wronging themselves. It also says <i>jamīʿan</i>: <b>all</b> sins.",
  "I kept the following verses so you have the full context. The mercy comes with urgency: turn back before the moment passes. Verse 56 is the voice of the soul that waited too long.",
 ]),
 (55, 1, 13, 1, "The All-Merciful taught the Qur'an", "ٱلرَّحۡمَٰنُ", [
  "The surah opens with the divine name standing alone as a complete verse. Our earlier finding showed that <i>al-Raḥmān</i> as a free-standing name is concentrated in the Meccan period, about 8.4 times its Medinan rate.",
  "Look at the order: teaching the Qur'an comes before creating the human. Then comes the measured cosmos, where the sun and moon run <i>bi-ḥusbān</i>, “by exact reckoning”. That is the counter's verse. Then the balance, which you are told three times not to violate, and the first of 31 refrains.",
  "Our source labels this surah Medinan, as the Egyptian standard muṣḥaf does. Many classical authorities hold that it is Meccan.",
 ]),
 (57, 1, 6, 3, "The First and the Last", "هُوَ ٱلۡأَوَّلُ وَٱلۡأٓخِرُ", [
  "This is the densest description of God's qualities in the book. Verse 3 gives First and Last, Manifest and Hidden in one breath. Verse 4 puts the Throne (transcendence) and <i>wa-huwa maʿakum ayna mā kuntum</i>, “and He is with you wherever you are” (immanence), in a single verse.",
  "It ends with night merging into day and day into night, and with His knowledge of what is in the hearts. That links it to the night and day passage above.",
 ]),
 (59, 20, 24, 22, "To Him belong the most beautiful names", "لَهُ ٱلۡأَسۡمَآءُ ٱلۡحُسۡنَىٰ", [
  "In three verses that each open with <i>huwa Allāh</i>, “He is God”, sixteen names and attributes follow one after another. Before them, verse 21 says a mountain would split from awe if this Qur'an were sent down on it.",
  "A note on method: our divine-names field counts epithets only at verse endings, so it under-counts this passage. When I asked the field for its densest windows, it returned legal passages in al-Baqara, where a name closes each ruling. The instrument decides what you find.",
 ]),
]

# themes of the hand-picked passages, keyed by (surah, first verse)
THEMES = {(2, 183): ["names", "mercy"], (13, 19): ["reward"], (28, 70): ["mercy", "names"], (39, 53): ["mercy"],
          (55, 1): ["mercy", "names"], (57, 1): ["names"], (59, 20): ["names", "reward"]}
