#!/usr/bin/env python3
"""
annotate_word_meanings.py
=========================
Add bracketed plain-English insertions to Donaldson word studies.
Preserves the original scholarly text, adds [clarifications] inline
so a general reader can follow along.

Adds a `plain` field to each word entry.

Run from repo root:
    python3 lds_pipeline/annotate_word_meanings.py
"""

import json
from pathlib import Path

DONA = Path(__file__).parent.parent / "library" / "donaldson"

# Keys: (filename, verse_str, idx)
# Values: the annotated plain text to store as `plain`
ANNOTATIONS = {

("1_john_1.json", "3", 0):
"Fellowship [koinonia in Greek] appears three times in this section (1:3, 1:6, 1:7). "
"In the New Testament it means a partnership in the work — [like branches grafted into a vine] "
"we have been grafted into the true vine and we have a promise of inheritance.",

("1_kings_2.json", "7", 0):
"Barzillai means 'my iron' [suggesting strength and reliability]. "
"He was a Gileadite leader who helped David defeat Absalom's rebellion. "
"Barzillai and Shimei both lived at Mahanaim. Shimei, instead of showing kindness to David "
"when he fled from Absalom, threw rocks at him and cursed him. "
"Barzillai, however, showed great kindness to David and those who had fled with him "
"by providing them with food and clothing. David asked Solomon to provide for the family "
"of Barzillai as repayment for his kindness.",

("1_timothy_1.json", "10", 0):
"Men-stealers [the Greek word] literally means 'to catch a person by the foot' — dragging them away "
"against their will. It refers to enslavers: kidnappers of free people, or those who "
"stole slaves belonging to someone else — slave-dealers of every kind. "
"By using this word, Paul strikes directly at the slave trade.",

("1_timothy_3.json", "8", 0):
"Filthy lucre [Greek: aischrokerdes] means greedy for material gain — a shameful hunger for money. "
"This matters for deacons because they would have had contact with the church's funds, "
"possibly distributing aid to the poor. Someone driven by greed had no business in that role.",

("2_nephi_15.json", "2", 0):
"Special grapevines [Hebrew: soreq] were the finest variety available, "
"more expensive than common grapes [Hebrew: gephen], known for producing exceptional wine. "
"The vineyard master also cleared stones, built walls and a watchtower, and carved a winepress "
"out of the rock — two stone basins where grapes were pressed and the juice collected below. "
"All of this preparation showed he expected a great harvest. "
"Getting bitter, wild grapes in return made the disappointment all the sharper.",

("abraham_5.json", "21", 0):
"Righteousness [Hebrew: tsedawkaw] carries four meanings: being right or upright, "
"justice, piety, and welfare. The meaning that received the most attention in Nauvoo "
"was the last — welfare. A contemporary rabbi defined it as 'the charitable righteousness "
"which makes the love of God, rather than the right of another, the ground of assisting him.' "
"In other words: righteousness isn't just about what others deserve — it's about what they need. "
"It ties directly to charity, which comes from above [see Moroni 7:48].",

("acts_14.json", "22", 0):
"Confirming [Greek: episthrizontes] means to make more firm — to give additional strength "
"to something already in place. Every time Luke uses this word in Acts, it describes "
"what Paul and his companions did for young congregations: going back, steadying, deepening "
"what had already begun. Not starting over — reinforcing.",

("acts_18.json", "2", 0):
"Aquila was a Jewish craftsman from Pontus [on the Black Sea coast], "
"apparently not yet a disciple at this point, though Jews from Pontus had been present "
"at Pentecost. Paul 'found' him [the Greek suggests a deliberate search] — "
"possibly because Jewish craftsmen in a new city naturally sought out others of the same trade. "
"Their shared work as tentmakers became the beginning of a deep partnership in ministry.",

("acts_18.json", "8", 0):
"Crispus, though a Jew and the ruler of the local synagogue, had a Latin name — "
"suggesting he moved in Roman as well as Jewish circles. Paul personally baptized him, "
"which was unusual [normally letting Silas and Timothy handle baptisms], "
"perhaps because of how significant his conversion was. "
"When the head of the synagogue walks out to follow Paul, it changes everything for that community.",

("acts_18.json", "17", 0):
"Beat him [Greek: etupton, 'began to beat him'] — the crowd lashed out at the new synagogue leader "
"since they couldn't reach Paul. What's remarkable is that this same Sosthenes "
"later appears as Paul's co-author in 1 Corinthians — someone who had sought to persecute Paul "
"became one of his closest colleagues.",

("acts_21.json", "31", 0):
"Came up [Greek: anebe, 'went up'] — naturally, given the uproar. "
"The Roman garrison kept extra soldiers posted during Jewish festivals, "
"stationed in the Tower of Antonia at the northwest corner of the temple, "
"connected to the temple courts by stairs [mentioned in verse 35]. "
"At the first sign of a riot, they came down fast — which is what saved Paul's life.",

("acts_28.json", "31", 0):
"Faith [Greek: pistis] carries several layers of meaning: accepting a message, "
"an act of obedience and faithfulness, and trust [from the Greek pisteuo, meaning to obey, trust, and hope]. "
"In legal and political settings, pistis meant loyalty to a patron who had proved trustworthy. "
"To have faith in Christ means to align yourself with him — not just to agree with facts about him, "
"but to remain steadfast in him.",

("acts_28.json", "31", 1):
"Law [Greek: nomos] refers primarily to the Torah [the first five books of scripture] "
"and the entire framework built around it. Paul uses it in several ways: "
"sometimes the written commandments, sometimes the traditions of the Jewish elders, "
"and sometimes the Law of Christ [Romans 7:22] — which supersedes both.",

("acts_28.json", "31", 2):
"Justification [Greek: dikaiosis] is the act of God declaring a person free from guilt "
"and acceptable to him. In Latter-day Saint thought, an act 'justified by the Spirit' "
"means it has been sealed by the Holy Spirit of Promise — ratified and approved by the Holy Ghost. "
"The ultimate justification is that sealing. "
"[See Romans 3:28; Galatians 2:16; 2 Nephi 2:5; Mosiah 14:11; D&C 20:30; Moses 6:60]",

("acts_28.json", "31", 3):
"Righteous [Greek: dikaios] means upright in the fullest sense — "
"keeping God's commands, living virtuously, treating others fairly. "
"In a narrower legal sense it means rendering to each person what is their due, "
"passing just judgment. The word describes someone genuinely aligned with God, "
"not just outwardly religious.",

("acts_28.json", "31", 4):
"Sanctification [Greek: hagiasmos] is the process of becoming a saint — "
"holy, spiritually clean, purged of sin. "
"The root word [hagiazo] means to separate something from ordinary use and dedicate it to God. "
"Latter-day Saint scripture teaches three things make it possible: "
"the Atonement of Jesus Christ [D&C 76:41-42], "
"the Holy Ghost who purifies the heart and gives an abhorrence of sin [Alma 13:12], "
"and sustained personal righteousness. It's not a single moment but a life's work.",

("acts_28.json", "31", 5):
"Works [Greek: ergon] means actions or deeds — things you actually do. "
"[a] An act, deed, thing done. "
"[b] A human act done without divine help — effort alone, apart from grace. "
"[c] In Paul's writings, often refers to the Jewish way of life, "
"the system of outward observance he contrasts with faith in Christ.",

("deuteronomy_6.json", "13", 0):
"The command is to reverentially fear [Hebrew: thou] Yahweh their God, and serve him, "
"and swear by his name. In the ancient world, people swore by the name of whoever "
"held authority over them — the person who mattered most to their lives. "
"Yahweh was to hold that place for each Israelite — not with a slavish fear, "
"but with the reverent love of someone who knows God always deals justly. "
"To 'swear by his name' was effectively an oath of allegiance: "
"as far as they were concerned, he alone was God.",

("ephesians_4.json", "3", 0):
"Peace [Greek: eirene] in the New Testament carries more than the absence of conflict — "
"it contains the meaning of unity and harmony, and translates the full range of the Hebrew shalom "
"[meaning wholeness and well-being in every dimension of life]. "
"That which is not peace lacks unity. Paul uses it here alongside 'the unity of the Spirit' [Ephesians 4:3] "
"and contrasts it with 'confusion' in 1 Corinthians 14:33: 'God is not the author of confusion, but of peace.'",

("exodus_21.json", "2", 0):
"Mishpatim [Hebrew: enactments, or ordinances] are legal rulings — case-by-case applications of law. "
"This code opens with ten laws regulating slavery, which is unusual: "
"no other law collection from the ancient Near East, including Hammurabi's, opens here. "
"The priority given to this subject almost certainly has a historical explanation: "
"Israel had just escaped bondage in Egypt. "
"The Torah insists they remember what it felt like. "
"Every slave is called 'your brother' in these laws; he has the right to rest on the Sabbath; "
"losing a limb at a master's hand wins him immediate freedom. "
"'He who buys a Hebrew slave,' the rabbis observed, 'is like one buying himself a master.'",

("exodus_39.json", "30", 0):
"Holiness [Hebrew: qodesh] means apartness — being set apart, reserved, sacred. "
"When something is declared holy, it is removed from ordinary use and dedicated entirely to God. "
"The high priest's crown bore this word as a constant reminder: "
"his life and work belonged wholly to the Lord.",

("ezekiel_48.json", "35", 0):
"Apocalyptic literature [Greek: is a style of prophetic writing] "
"that uses vivid imagery, symbolic numbers, and dramatic visions to describe "
"the ultimate triumph of God over evil. "
"Its roots are mainly Jewish, growing out of prophetic literature — both share "
"the inspiration of the Divine Spirit and the belief in God's ultimate reign. "
"It appears early in Isaiah 24-27, Jeremiah 24, Ezekiel 1-37, Joel, and Zechariah 12-14, "
"and reached full expression in Daniel and Revelation. "
"Jesus drew on its thought forms regularly [Matthew 25:31-46].",

("isaiah_1.json", "27", 0):
"Captives [Hebrew: shuwb] means those who return or are brought back — "
"not 'converts' as the KJV has it, which is not supported by any other reading. "
"Isaiah is describing God bringing back those who were carried away into exile, "
"not simply people who changed their minds.",

("isaiah_5.json", "2", 0):
"Special grapevines [Hebrew: soreq] were the finest variety available, "
"more expensive than common grapes [Hebrew: gephen], known for producing exceptional wine. "
"The vineyard master also cleared stones, built walls and a watchtower, and carved a winepress "
"out of the rock — two stone basins where grapes were pressed and the juice collected below. "
"All of this preparation showed he expected a great harvest. "
"Getting bitter, wild grapes in return made the disappointment all the sharper.",

("john_1.json", "1", 0):
"'Was' [Greek: en, from the verb eimi meaning 'to be'] appears three times in this opening sentence. "
"This form of the verb conveys no idea of origin — simply continuous existence, with no beginning. "
"A completely different verb [ginomai, meaning 'became' or 'came into being'] appears in verse 14 "
"to mark the moment the Word entered the world as flesh. "
"The contrast is sharpest in John 8:58: 'Before Abraham came into being [ginomai] — I am [eimi, timeless].'",

("john_1.json", "1", 1):
"The Word [Greek: logos, from the verb lego meaning 'to speak' or 'to put words together'] "
"carried enormous weight in the ancient world. "
"[For Greek philosophers] logos meant the rational principle behind the universe — "
"Heraclitus used it for the force that controls everything, the Stoics for the soul of the world, "
"Marcus Aurelius for the generative principle in nature. "
"[For Jewish thinkers] the Hebrew memra described God's active presence and wisdom made visible — "
"like the Angel of the Lord or the Wisdom of God in Proverbs 8:23. "
"John takes both traditions and says: that force, that presence, that living reason — is a person.",

("john_17.json", "17", 0):
"Sanctify [Greek: hagiazo] means to make holy — to set something apart and consecrate it "
"for a sacred purpose, marking it as belonging to God. "
"When Jesus asks the Father to sanctify his disciples through truth, "
"he's asking that they be consecrated: set apart, made ready for the work he's sending them to do.",

("john_18.json", "28", 0):
"Palace [Greek: praetorium] was the name for a Roman governor's official residence. "
"Here it probably refers to the magnificent palace in Jerusalem built by Herod the Great, "
"occupied by the Roman Procurator [governor] when he came to the city — "
"one of the grandest buildings in the ancient world. "
"The Jewish leaders refused to enter it during Passover to avoid ritual contamination, "
"so Pilate had to come outside to meet them.",

("john_21.json", "25", 0):
"Faith [Greek: pistis] carries several layers of meaning: accepting a message, "
"an act of obedience and faithfulness, and trust [from pisteuo, meaning to obey, trust, and hope]. "
"To have faith in Christ means to align yourself with him — not just to agree with facts about him, "
"but to remain steadfast in him.",

("john_21.json", "25", 1):
"Law [Greek: nomos] refers primarily to the Torah [the first five books of scripture] "
"and the entire framework built around it. Paul uses it in several ways: "
"sometimes the written commandments, sometimes the traditions of the Jewish elders, "
"and sometimes the Law of Christ [Romans 7:22].",

("john_21.json", "25", 2):
"Justification [Greek: dikaiosis] is the act of God declaring a person free from guilt "
"and acceptable to him. In Latter-day Saint thought, the ultimate justification "
"is being sealed by the Holy Spirit of Promise — ratified and approved by the Holy Ghost.",

("john_21.json", "25", 3):
"Righteous [Greek: dikaios] means upright and virtuous in the fullest sense — "
"keeping God's commands, treating others fairly, and standing in right relationship with God. "
"The word describes someone genuinely aligned with God, not just outwardly religious.",

("john_21.json", "25", 4):
"Sanctification [Greek: hagiasmos] is the process of becoming a saint — "
"holy, spiritually clean, purged of sin. "
"The root [hagiazo] means to separate from ordinary use and dedicate to God. "
"Three things make it possible: the Atonement of Christ, the purifying work of the Holy Ghost, "
"and sustained personal righteousness. It's not a single moment but a life's work.",

("john_21.json", "25", 5):
"Works [Greek: ergon] means actions or deeds — things you actually do. "
"In Paul's writings it often refers to human effort alone, apart from grace, "
"or to the Jewish system of outward observance. James uses the same word to insist "
"that genuine faith always shows itself in how you live.",

("john_4.json", "7", 0):
"Samaritans [Greek: are a group] who considered themselves descendants of the original Israelite tribes, "
"but broke away in the 11th century BCE over the location of true worship. "
"They insisted Mount Gerizim near Shechem was the place God chose — not Jerusalem. "
"They accepted only the Five Books of Moses and rejected all later Jewish writings. "
"Jews and Samaritans had deep mutual distrust, so when Jesus asked a Samaritan woman for water, "
"it broke several social rules at once.",

("john_4.json", "19", 0):
"I perceive [Greek: theoreo, 'I am beginning to perceive'] — "
"the Greek captures something subtle: she doesn't suddenly know. "
"The recognition is dawning on her, the understanding unfolding gradually rather than arriving all at once.",

("john_6.json", "10", 0):
"Sit down [Greek: anapesein, literally 'fall back'] means to recline — "
"the normal posture for eating in the ancient world. "
"People didn't sit upright at tables; they lay on mats or cushions, leaning on one elbow. "
"The feeding of the five thousand takes on the quality of a formal meal.",

("john_6.json", "15", 0):
"Take him by force [Greek: arpazein] describes aggressive, forcible seizing — "
"the same word used for violent seizure elsewhere [Matthew 11:12; 13:19]. "
"The crowd wanted to grab Jesus and declare him king, starting a revolt against Roman rule. "
"Jesus saw it coming and slipped away, because his kingdom doesn't work that way.",

("john_6.json", "52", 0):
"Strove [Greek: emachonto] — the word originally meant fighting in armed combat, "
"then came to mean waging a war of words. "
"The crowd wasn't just puzzled by what Jesus said — they broke into heated argument with each other, "
"some taking his words literally, some sensing something deeper. "
"This kind of division followed Jesus everywhere [see John 7:12, 40; 9:16; 10:19].",

("john_7.json", "1", 0):
"Walked [Greek: periepatei, 'was walking around'] — "
"the Greek tense gives a picture of ongoing, repeated movement: "
"Jesus traveling from place to place, teaching as he went. "
"He had been deliberately staying away from both Galilee and Judea for six months, "
"avoiding leaders who wanted to arrest him. His movement was purposeful.",

("john_7.json", "11", 0):
"Sought [Greek: ezhtoun, 'were seeking'] — "
"the tense shows this was ongoing, continuous action. "
"The Jewish leaders weren't just looking for Jesus at that moment — "
"they had been watching and waiting. He hadn't been to Jerusalem since a confrontation in chapter 5, "
"and they were ready for him.",

("john_7.json", "12", 0):
"A good man [Greek: agathos] means good in motive — pure from the inside out, "
"not just in outward behavior. "
"Paul uses this word in Romans 5:7 in the absolute sense, reserved for God himself. "
"When the crowds call Jesus 'a good man,' they're using a word that carries more weight than they realize.",

("john_8.json", "4", 0):
"In adultery [Greek: moicheuomene, 'herself suffering adultery'] — "
"the Greek describes the woman as a passive recipient: someone to whom this act was being done. "
"She was caught and brought forward as bait for a legal trap against Jesus. "
"The man involved is conspicuously absent from the scene.",

("john_8.json", "7", 0):
"He lifted himself up [Greek: anekupsen, the opposite of bending down] — "
"Jesus had been bent over, writing in the dust. Now he straightens up and looks directly at the accusers. "
"The physical gesture matches the weight of what he's about to say: a shift from silence to direct confrontation.",

("joshua_1.json", "10", 0):
"Officers [Hebrew: shoterim] were the senior tribal leaders — "
"chief men responsible for organizing and directing large groups. "
"They served alongside the judges [mentioned in Deuteronomy 16:18], "
"handling the practical side of leadership: logistics, communication, giving orders. "
"Joshua goes to them first before moving the entire nation.",

("leviticus_13.json", "2", 0):
"Leprosy [Hebrew root: tzarah, meaning 'to smite heavily'] — "
"a person with this condition was thought to have been 'smitten, scourged of God.' "
"The term covered a broad range of skin conditions and even decay in objects like mildew or dry rot — "
"not just what we call leprosy today. The common thread was visible deterioration. "
"Because of this, leprosy became a symbol of sin: something that corrupts from the inside out "
"and eventually shows on the surface.",

("luke_10.json", "11", 0):
"Cleaveth [Greek: kollethenta] — the word describes how dust and mud cling to sandals. "
"Shaking it off was a deliberate, public gesture of separation: "
"we've left your community entirely behind, and even the dust from your streets "
"is no longer ours to carry.",

("luke_10.json", "11", 1):
"We wipe off [Greek: apomassometha] means to rub something off with the hands — "
"an emphatic, deliberate act. Combined with the dust imagery, it signals a complete break. "
"The disciples aren't retreating; they're making a clear, public statement of rejection.",

("luke_10.json", "35", 0):
"Two pence [Greek: denarii — two days' wages] would cover several days of food and lodging "
"for a sick man. The innkeeper is promised repayment 'when I return,' "
"which may echo the three-day pattern found throughout the Gospels. "
"Either way, the provision is specific, generous, and carefully calculated.",

("luke_13.json", "12", 0):
"Thou art loosed [Greek: apolelusai, perfect tense — 'loosed to stay free']. "
"The tense indicates a permanent state: she isn't just temporarily freed — she is free, and the freedom holds. "
"Jesus speaks this before he even touches her. The healing begins with a declaration.",

("luke_14.json", "16", 0):
"Great supper [Greek: deipnon] — the main meal of the day, a formal dinner. "
"In the ancient world, invitations to such feasts were an honor, and declining was a serious offense. "
"Jesus uses this setting to describe how God's invitation to his kingdom is extended broadly — "
"and how readily people find excuses to turn it down.",

("luke_15.json", "5", 0):
"Rejoicing [Greek: chairon] — the shepherd doesn't scold the sheep or grumble about the trouble. "
"As one commentator put it: 'There is no upbraiding of the wandering sheep, nor murmuring at the trouble.' "
"He simply comes home rejoicing. Pure, uncomplicated happiness — no resentment attached, no lecture waiting. "
"That's the point.",

("luke_15.json", "13", 0):
"Wasted [Greek: dieskorpisen] literally means to scatter — "
"like grain thrown to the wind [the same word used for winnowing grain in Matthew 25:24]. "
"The son didn't just spend his money; he dispersed it in all directions, carelessly and completely. "
"It's the opposite of gathering, the opposite of stewardship.",

("luke_15.json", "18", 0):
"I did sin [Greek: hemarton] — the word means to miss the mark, to aim at the right thing and fall short. "
"'That is the hard word to say,' notes one commentator, 'and he will say it first.' "
"This is the turning point: not just regretting his situation, but naming what he did. "
"That's what repentance looks like.",

("luke_15.json", "20", 0):
"Kissed [Greek: katephilesen] — an intensified form of the word: "
"not one kiss but a burst of repeated kisses [literally: kissed him again and again], "
"an overwhelming expression of love. "
"The father doesn't hold back, doesn't wait for the speech to be finished. "
"He runs, embraces, and kisses. The welcome comes before the apology is complete.",

("luke_15.json", "22", 0):
"Shoes [Greek: hypodema, sandals, literally 'bound under'] — "
"sandals were a mark of freedom. Slaves went barefoot. "
"By putting shoes on his son's feet, the father declares publicly: "
"this person is not a servant in my house. He is a son — fully restored.",

("luke_15.json", "23", 0):
"Kill [Greek: thysate] — not as a sacrifice, but for a feast. "
"The fattened calf was the finest food available, reserved for the most special occasions. "
"The father doesn't plan a modest welcome. He throws the best celebration the household can produce.",

("luke_15.json", "28", 0):
"He was angry [Greek: orgisthe — 'he flew into a rage']. "
"The word describes a sudden eruption — long-held resentment finally breaking open. "
"The older son had kept this in for years. Seeing the celebration for his brother "
"brought it all to the surface at once.",

("luke_15.json", "30", 0):
"Came [Greek: elthen] — 'he does not even say, came back or came home.' "
"The older son says only 'came' — refusing to acknowledge that this is his brother's home, "
"or that the return means anything. He keeps his distance even in the language he uses.",

("luke_15.json", "30", 1):
"Devoured [Greek: kataphagon — 'eaten down'] — "
"we say 'eaten up,' but the Greek uses kata [meaning 'down'], implying total consumption. "
"The word is loaded with bitterness: the older son is describing his brother's spending "
"as complete destruction.",

("luke_15.json", "31", 0):
"Thou [Greek: su — the personal pronoun expressed explicitly for emphasis]. "
"In Greek, 'you' is usually implied in the verb and left out. When it's added, it's emphatic — "
"like leaning on the word. The father singles out the son: you specifically, all along, have had everything. "
"The emphasis is gentle but pointed.",

("luke_15.json", "32", 0):
"It was meet [Greek: edei — 'it was necessary']. "
"Not a choice — a necessity. The father isn't defending himself; he's explaining what joy requires. "
"When someone who was dead is alive again, when someone who was lost is found, "
"celebration is not optional. It's the only fitting response.",

("luke_17.json", "10", 0):
"Unprofitable [Greek: achreioi — literally 'having gained nothing extra']. "
"The word describes a slave who has only done what was commanded — "
"he has earned no bonus credit, no merit beyond the requirement. "
"Jesus isn't calling his disciples worthless; he's saying that faithful obedience "
"is the baseline, not an achievement deserving a reward. We don't put God in our debt by doing what he asks.",

("luke_18.json", "35", 0):
"Begging [Greek: epaiton] means asking for something — "
"and the man's position by the wayside was strategic. "
"He was likely between the old city of Jericho and the new Roman Jericho, "
"where travelers had to pass. Beggars claimed their spots carefully. "
"This man heard the crowd coming and called out immediately — he had learned to read the sound of opportunity.",

("luke_2.json", "16", 0):
"Found [Greek: aneurisko — a compound that suggests searching before finding]. "
"The shepherds didn't walk in and immediately see the baby. They looked, they asked, they searched. "
"The finding is more meaningful because of the seeking.",

("luke_2.json", "28", 0):
"Arms [Greek: agkale] — the word refers specifically to the inner curve of the arms, "
"the natural cradle formed when you hold something close to your chest. "
"This is the most vulnerable part of the arm — the place of greatest protection. "
"Simeon didn't just take the child; he drew him into the most sheltered place possible.",

("luke_2.json", "48", 0):
"They were astonished [Greek: ekplesso — literally 'struck out'] — "
"the word describes being hit so hard you're knocked out of your normal state. "
"Joseph and Mary 'were struck out' by what they saw and heard. "
"Even they, who had been told from the beginning who this child was, "
"were stopped cold by seeing him in the temple, holding his own among the teachers.",

("luke_2.json", "49", 0):
"Father [Greek: pater] — Jesus calls God 'Father,' and the word tells you everything. "
"In the ancient world, a father's house was where you belonged, where your work was, "
"where your loyalty lay. Jesus is twelve years old, and already he knows exactly whose house this is "
"and where he needs to be.",

("luke_22.json", "1", 0):
"Passover [Greek: pascha] commemorated the night Israel escaped Egypt — "
"the defining event of Jewish history. The Feast of Unleavened Bread followed immediately after, "
"so the two were often spoken of together. "
"Everything Jesus is about to do over the next several days will be interpreted through this night: "
"deliverance from bondage through a sacrifice.",

("luke_22.json", "41", 0):
"Prayed [Greek: prosecheto — 'was praying, kept on praying']. "
"The Greek shows ongoing, continuous prayer — not a single petition but sustained, repeated prayer. "
"In Gethsemane, Jesus doesn't pray once and move on. He keeps returning to the Father, "
"pouring out his anguish again and again. The weight of what's coming required more than one prayer.",

("luke_3.json", "11", 0):
"Coats [Greek: chiton] was the inner undergarment — less essential than the outer robe. "
"John's instruction is specific: if you have two of even the basic layer, give one away. "
"Not surplus luxury — what you could technically spare. "
"Note the different message to each group: to the people, don't hoard what isn't essential; "
"to tax collectors, don't extract more than required; to soldiers, no violence, no false accusations.",

("luke_4.json", "14", 0):
"Returned [Greek: hypestrepsen] — Luke moves straight from the wilderness temptations "
"to the public ministry in Galilee with one word. Whatever happened in between — "
"recovery, preparation, further prayer — Luke doesn't linger on it. "
"The emphasis is entirely on what comes next: Jesus going public.",

("luke_4.json", "16", 0):
"Stood up [Greek: aneste] — standing was the customary posture for reading scripture aloud in the synagogue. "
"The congregation sat; the reader stood. "
"It was his habit to go to the synagogue on the Sabbath. "
"He may have been invited to read, as Paul was at Antioch in Pisidia [Acts 13:15]. "
"The moment he opens his mouth to speak afterward, everything changes.",

("luke_4.json", "17", 0):
"Was delivered [Greek: epedothe — 'given over to'] — "
"the synagogue attendant took the scroll from the ark and handed it to someone to read. "
"On Sabbaths, seven persons were typically asked to read small portions of the Law [the Parashah]. "
"This was followed by a reading from the Prophets and a discourse [the Haphtarah]. "
"What Jesus does here is the Haphtarah — the second lesson — and then he sits down to teach.",

("luke_4.json", "18", 0):
"Set at liberty [Greek: aposteilai — from the same root as 'apostle']. "
"The word means to send out, release, dispatch. "
"Isaiah's prophecy describes someone sent to release captives. "
"Jesus reads this aloud and then announces it is fulfilled today — "
"declaring himself the one sent to set people free.",

("luke_4.json", "18", 1):
"Them that are bruised [Greek: tetrausmenous] means broken — not just injured but shattered, in pieces. "
"The word describes people crushed in body, in spirit, in dignity. "
"Jesus is sent specifically to them. This is the core of his mission statement: "
"he doesn't come for the already-fine.",

("luke_4.json", "20", 0):
"Sat down [Greek: ekathisen] — sitting was the signal that teaching was about to begin. "
"The teacher sat, the students listened. "
"The usual Jewish posture for public speaking and teaching [see Luke 5:3; Matthew 5:1; Mark 4:1]. "
"Every eye in the room locked onto him. The sentence that followed landed into complete silence.",

("luke_4.json", "21", 0):
"Hath been fulfilled [Greek: peplerothe — perfect tense: 'stands fulfilled right now']. "
"Jesus doesn't say the prophecy 'was' fulfilled in the past — "
"he says it stands fulfilled, present and ongoing. "
"In one sentence he claims to be the person Isaiah described: "
"the Messiah who forgives sin and binds up the broken-hearted. "
"The people of Nazareth were quick to see exactly what he was claiming.",

("luke_5.json", "1", 0):
"The Sea of Galilee [Greek: the word fresh here describes these bodies of water] "
"is quite large for the Middle East — about 13 miles from north to south, "
"and 7½ miles east to west at its widest. "
"The Jordan River flows through it, entering in the north and exiting in the south. "
"It was the working center of the local fishing economy.",

("luke_5.json", "5", 0):
"Master [Greek: epistata — superintendent or overseer, someone with authority over others]. "
"Luke alone uses this word for Jesus in the New Testament, always in direct address [Luke 8:24, 45; 9:33, 49; 17:13]. "
"It's different from 'Rabbi' [teacher] used in the other Gospels — "
"Simon is recognizing not just Jesus's knowledge but his authority. "
"Even when Jesus's instruction seems impractical, Simon obeys it.",

("luke_5.json", "5", 1):
"We toiled [Greek: kopiasantes — from kopos, exhausting labor]. "
"The word carries the idea of weariness, not just effort. "
"Peter and the others had been at it all night with nothing to show for it. "
"The context makes what follows more startling: these are experienced fishermen, and they failed. "
"Then a carpenter tells them where to put the nets.",

("luke_5.json", "6", 0):
"Were breaking [Greek: dierrsseto — the nets were actually tearing in two]. "
"If the nets gave way, the catch would be lost entirely. "
"The miracle immediately threatened to undo itself — which is why they called for help so urgently. "
"Even the blessing required fast action.",

("luke_5.json", "7", 0):
"They beckoned [Greek: kateneusan — made signs]. "
"The other boat was too far away to hear a shout, so they used hand signals. "
"'Some are also too far away and signs are given, beckoning them to come to the Master.' "
"The frantic gesture captures the chaos of the moment.",

("luke_5.json", "15", 0):
"Went abroad [Greek: diercheto — 'kept going,' imperfect tense]. "
"The fame of Jesus spread continuously, moving out in all directions without stopping. "
"The more Jesus told people to keep quiet, the more they talked. "
"His reputation was traveling faster than he was.",

("luke_5.json", "15", 1):
"Came together [Greek: synrchonto — 'kept coming,' imperfect tense again]. "
"The crowds kept arriving — not a single gathering but a steady, growing flow. "
"As the news spread outward, it pulled people inward toward wherever Jesus was.",

("luke_5.json", "17", 0):
"Doctors of the law [Greek: nomodidaskaloi — teachers and interpreters of the Law]. "
"The same people Matthew and Mark call 'scribes.' "
"Our word 'doctor' comes from the Latin for teacher. "
"They were usually Pharisees, though not all Pharisees were law teachers. "
"By this point they've come from Jerusalem specifically to observe Jesus — "
"their presence raises the stakes of everything he does.",

("luke_5.json", "26", 0):
"Amazement [Greek: ekstasis — source of our word 'ecstasy']. "
"The word describes being knocked out of your normal mental state by shock and wonder. "
"The crowd was so overwhelmed they didn't know how to process it — "
"glorifying God and filled with fear at the same time.",

("luke_5.json", "26", 1):
"Strange things [Greek: paradoxa — source of our word 'paradox']. "
"It means something contrary to received opinion — outside the range of normal expectation. "
"The crowd uses it because what they witnessed didn't fit any category they had. "
"It wasn't just impressive; it was entirely outside the range of normal experience.",

("luke_6.json", "9", 0):
"A life [Greek: psuchen — soul or life, the whole person]. "
"Jewish law held that a Jewish life in danger overrides the Sabbath. "
"Jesus sharpens the question: is it lawful to save a life on the Sabbath? "
"He's not just asking about a withered hand — "
"he's asking what the Sabbath is ultimately for.",

("luke_6.json", "11", 0):
"Communed [Greek: dielaloun — heated, excited conversation back and forth]. "
"The Pharisees didn't calmly discuss options. They bolted out of the synagogue "
"and immediately began plotting with the Herodians [a political group they normally despised] "
"to figure out how to destroy Jesus.",

("luke_6.json", "21", 0):
"Now [Greek: nun] — Luke adds this adverb that Matthew's version doesn't have. "
"It sharpens the contrast deliberately: those who hunger now will be filled. "
"Those who weep now will laugh. The 'now' makes clear that the present condition is temporary — "
"the reversal is coming.",

("luke_6.json", "25", 0):
"Now [Greek: nun] — the same word appears twice here in the woes that mirror the blessings. "
"Those who are rich now, satisfied now, laughing now — "
"the 'now' carries a warning: what you're enjoying in the present is all you're getting. "
"The future belongs to those who endured.",

("luke_6.json", "42", 0):
"Thou hypocrite [Greek: hypokrita — literally 'actor, one playing a role']. "
"The word originally described a stage performer pretending to be someone they're not. "
"Jesus switches from the gentle 'brother' of a moment ago to this word, "
"stripping away the pretense. The person trying to remove the speck from another's eye "
"is performing concern, not feeling it.",

("luke_6.json", "44", 0):
"Is known [Greek: ginosketai — to know by direct experience, not theory]. "
"You don't guess what kind of tree it is — you taste the fruit and you know. "
"The fruit test is the final test. Character eventually shows itself in what a person produces.",

("luke_6.json", "44", 1):
"Gather [Greek: trygousin] — the word specifically means harvesting ripe fruit, "
"gathering what has fully come to maturity. "
"You don't harvest thorns; you harvest what was grown to be harvested. "
"Character produces its own appropriate results.",

("luke_7.json", "41", 0):
"Debtors [Greek: chreophiletai — from chreos, debt or obligation, and opheilein, to owe]. "
"The parable uses the language of financial debt to describe moral debt — "
"sin as something you owe that you can't repay yourself. "
"The question: which debtor would love more after having the debt cancelled?",

("luke_7.json", "43", 0):
"Rightly [Greek: orthos — correctly, having reasoned it through to the right answer]. "
"The Pharisee answers Jesus's question correctly. Jesus affirms it immediately. "
"He got the intellectual answer right. The harder question is whether he'll apply it to himself.",

("luke_7.json", "46", 0):
"With ointment [Greek: muron — costly perfumed oil]. "
"It was used for special occasions like weddings or honorable burials. "
"The woman used it for the feet — an even more extravagant act of humility than anointing the head. "
"Simon had given Jesus none of the normal marks of welcome; she gave him everything.",

("luke_7.json", "48", 0):
"Are forgiven [Greek: apheontai — present tense: 'remain forgiven, stand forgiven']. "
"Jesus doesn't say 'I forgave you earlier' — the forgiveness is present tense, still in effect. "
"In spite of Simon's silent judgment, the forgiveness holds.",

("mark_10.json", "17", 0):
"Ran [Greek: prosdramown] — Jesus had left the house and was walking along the road "
"when this man ran up and knelt before him [both details appear only in Mark]. "
"He was asking [imperfect tense — kept asking] Jesus about his problem. "
"The eagerness of the approach stands in contrast to what Jesus is about to tell him.",

("mark_10.json", "23", 0):
"Looked round about [Greek: periblepsemenos — a sweeping look around the circle]. "
"This detail appears in Mark alone, as in 3:5 and 3:34. "
"When the rich young man had gone, Jesus's eye moved around the Twelve, "
"drawing from the encounter a lesson for them: "
"'When the man was gone the Lord's eye swept round the circle of the Twelve, "
"as he drew for them the lesson of the incident.'",

("matthew_18.json", "6", 0):
"Millstone [Greek: mulos] — this was a large grinding stone consisting of two heavy pieces: "
"an upper stone that rotated, and a fixed lower one. "
"The kind mentioned here [mulos onikos, a 'donkey millstone'] was the large commercial variety, "
"turned by a donkey, too heavy for a person to lift. "
"The image makes the point vividly: better to be drowned under that weight "
"than to cause a child to stumble.",

("matthew_22.json", "5", 0):
"Made light of it [Greek: amelesantes — neglecting, not caring for]. "
"The word doesn't say they ridiculed the invitation — they simply ignored it, "
"treating it as unimportant. But to neglect an invitation to a wedding feast in the ancient world "
"was a serious social offense, not a casual slight.",

("matthew_5.json", "17", 0):
"Law [Hebrew: Torah] and the Prophets [Hebrew: Nevi'im] together make up two of the three sections "
"of the Hebrew Bible. The third is the Writings [Hebrew: Ketuvim — Psalms, Proverbs, and others]. "
"When Jesus says he came not to destroy 'the Law and the Prophets,' "
"he's referring to essentially the entire Hebrew scripture.",

("matthew_6.json", "7", 0):
"Use not vain repetitions [Greek: battologeo — to babble, to repeat empty words]. "
"The word is probably onomatopoetic [its sound echoes its meaning, like 'babble']. "
"The worshippers of Baal on Mount Carmel [1 Kings 18:26] and the crowd at Ephesus "
"who chanted 'Great is Diana' for two hours [Acts 19:34] are examples. "
"Jesus isn't forbidding persistence — he's forbidding mindless repetition that mistakes volume for prayer.",

("matthew_6.json", "19", 0):
"Break through [Greek: diorusso — literally 'dig through']. "
"Ancient houses had walls of mud brick or sun-dried clay — easy to dig through. "
"The Greeks called a burglar a 'mud-digger.' "
"Jesus's point: no physical storage is secure. Don't invest your heart in what can be taken.",

("matthew_6.json", "20", 0):
"Rust [Greek: brosis — literally 'something that eats'] — "
"the word means what gnaws, corrodes, or consumes from within. "
"It applies to more than rust: anything that slowly destroys stored treasure — "
"moths, rot, decay. The point is that earthly things deteriorate by their nature.",

("matthew_7.json", "5", 0):
"Shalt thou see clearly [Greek: diablepsis — to look through, to penetrate clearly]. "
"The word contrasts with merely gazing [blepeis, verse 3]. "
"Get the plank out of your own eye, and then — only then — "
"you'll actually see clearly enough to help your brother with the splinter in his.",

("moroni_10.json", "34", 0):
"Inductive [and objective] searching, by definition, demands thoroughness. "
"Using concordances like the Topical Guide, we can identify relevant scriptures on the family. "
"The extended family in ancient scripture is recognized as a unit here on earth and in the hereafter — "
"the word family generally refers to lineage and extended kinship, "
"while household [Mosiah 2:5; Joshua 7:14] refers to the conjugal unit. "
"These family relationships require the sealing ordinance [the 'welding link,' Malachi 4:6; D&C 2:2] "
"to be established forever beyond this life.",

("moroni_4.json", "3", 0):
"That they may eat [and drink] in remembrance — "
"the emblems of the sacrament are symbols of the Savior's flesh and blood, "
"offered in the infinite and eternal Atonement. "
"Their symbolic nature is taught clearly in scripture "
"[see JST Matthew 26:22-25; 3 Nephi 18:7-10]. "
"We take them not as the literal body and blood [as some Christian traditions teach] "
"but as sacred emblems of the covenant.",

("mosiah_12.json", "2", 0):
"Stretch forth [Hebrew: shalach] means to send, send away, or let go. "
"This is a warning prophecy: if Israel does not repent, the Lord will release his hold — "
"he will 'let go,' withdraw his protecting hand. "
"But the word also implies a choice: the Lord extends his hand, "
"and they decide whether to take hold of it.",

("philippians_2.json", "2", 0):
"Fulfill [Greek: pleroson — make full, fill up completely]. "
"Paul's joy is bound up entirely with how the Philippians are living and advancing the gospel. "
"He's not asking them to add to an empty thing — he's asking them to fill it out completely, "
"to bring it to its full measure.",

("psalms_53.json", "1", 0):
"Mahalath [Hebrew: machalath — meaning 'sickness' or possibly a musical term]. "
"It appears in the psalm's heading and may identify the tune to which this lament was sung — "
"a song of sickness, of spiritual mourning. The psalm itself describes a world that has turned away from God.",

("revelation_6.json", "4", 0):
"A red horse [Greek: pyrrhos, fiery red] is associated with war and bloodshed. "
"One scholar suggests this represents international strife and conflict between nations. "
"LDS commentators have proposed associations with the time of Noah. "
"Another reads it as representing the social upheaval caused by Roman military power "
"in the era when Revelation was written.",

("revelation_6.json", "8", 0):
"Death [Greek: thanatos — the death of the body, from thnesko, 'to die']. "
"This is physical death, the end of mortal life. "
"In Revelation, Death rides as a figure alongside Hades [the realm of the dead] — "
"together they are given power over a quarter of the earth.",

("zechariah_10.json", "8", 0):
"I will hiss [Hebrew: sharaq — to whistle or signal]. "
"The image is a shepherd whistling for scattered sheep, who then come running back to the flock. "
"God is pictured here as gathering his scattered people with a shepherd's call — "
"not driving them by force, but calling, and they come with speed.",

}


def main():
    updated = 0
    by_file: dict[Path, dict] = {}

    for (filename, verse, idx), plain in ANNOTATIONS.items():
        fp = DONA / filename
        if fp not in by_file:
            if not fp.exists():
                print(f"MISSING: {fp}")
                continue
            by_file[fp] = json.loads(fp.read_text(encoding="utf-8"))

        data = by_file[fp]
        entry = data.get(verse, {})
        words = entry.get("words", [])
        if idx < len(words):
            words[idx]["plain"] = plain
            updated += 1
        else:
            print(f"WARN: {filename} v{verse} idx={idx} out of range (len={len(words)})")

    for fp, data in by_file.items():
        fp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    print(f"Annotated {updated} word entries across {len(by_file)} files.")


if __name__ == "__main__":
    main()
