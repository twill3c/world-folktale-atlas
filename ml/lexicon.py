"""語彙表 — 数え上げで決まるものと、推定でしか出ないものを分ける。

**この二つを同じ見た目で並べてはならない**(SPEC F-14 / G-08)。

  数え上げ(exact)  : 動物・自然物・出来事の引き金語。本文にその語があるかどうか。
                      confidence は 1.0 であり、根拠は「その語が何回出たか」で示せる。
  推定(estimated) : テーマ・モチーフ。Embedding との近さで出す。confidence は相対値。

語彙は英語とドイツ語の両方を持つ。コーパスは英語 299 話・ドイツ語 62 話である。
"""
from __future__ import annotations

#: 動物(設計書 §17)。値は (英語, ドイツ語) の異形
ANIMALS: dict[str, list[str]] = {
    "狼": ["wolf", "wolves", "wolf", "wölfe"],
    "狐": ["fox", "foxes", "fuchs", "füchse"],
    "熊": ["bear", "bears", "bär", "bären"],
    "鳥": ["bird", "birds", "vogel", "vögel"],
    "蛇": ["snake", "snakes", "serpent", "schlange", "schlangen"],
    "馬": ["horse", "horses", "pferd", "pferde", "ross"],
    "魚": ["fish", "fishes", "fisch", "fische"],
    "鷲": ["eagle", "eagles", "adler"],
    "烏": ["raven", "ravens", "crow", "crows", "rabe", "raben", "krähe"],
    "鹿": ["deer", "stag", "hirsch", "reh"],
    "猿": ["monkey", "monkeys", "ape", "affe", "affen"],
    "犬": ["dog", "dogs", "hound", "hund", "hunde"],
    "猫": ["cat", "cats", "katze", "katzen"],
    "兎": ["hare", "rabbit", "hase", "kaninchen"],
    "亀": ["tortoise", "turtle", "schildkröte"],
    "蜘蛛": ["spider", "spiders", "spinne"],
    "虎": ["tiger", "tigers", "tiger"],
    "獅子": ["lion", "lions", "löwe", "löwen"],
    "象": ["elephant", "elephants", "elefant"],
    "牛": ["ox", "oxen", "cow", "cows", "bull", "ochs", "kuh", "kühe"],
    "山羊": ["goat", "goats", "ziege", "ziegen", "geiß", "geißlein"],
    "鼠": ["mouse", "mice", "rat", "maus", "mäuse", "ratte"],
}

#: 自然物(設計書 §17)
NATURE: dict[str, list[str]] = {
    "山": ["mountain", "mountains", "hill", "berg", "berge"],
    "森": ["forest", "wood", "woods", "wald", "walde", "wälder"],
    "川": ["river", "stream", "fluss", "bach"],
    "海": ["sea", "ocean", "meer", "see"],
    "火": ["fire", "flame", "feuer", "flamme"],
    "雪": ["snow", "schnee"],
    "月": ["moon", "mond"],
    "太陽": ["sun", "sonne"],
    "雷": ["thunder", "lightning", "donner", "blitz"],
    "風": ["wind", "storm", "wind", "sturm"],
    "石": ["stone", "rock", "stein", "felsen"],
    "木": ["tree", "trees", "baum", "bäume"],
}

#: 物語イベントの引き金語(設計書 §13 のイベント語彙)
EVENT_TRIGGERS: dict[str, list[str]] = {
    "Birth": ["born", "birth", "child was born", "geboren", "geburt"],
    "Family": ["father", "mother", "brother", "sister", "vater", "mutter", "bruder", "schwester"],
    "Departure": ["set out", "left home", "journeyed forth", "went away", "zog aus",
                  "machte sich auf", "ging fort"],
    "Journey": ["travelled", "traveled", "wandered", "road", "wanderte", "reiste", "weg"],
    "Encounter": ["met", "came upon", "found a", "traf", "begegnete", "fand"],
    "Trial": ["task", "trial", "test", "must", "aufgabe", "prüfung", "musste"],
    "Gift": ["gave him", "gave her", "present", "gift", "schenkte", "gab ihm", "geschenk"],
    "Transformation": ["turned into", "changed into", "became a", "verwandelt", "wurde zu"],
    "Conflict": ["quarrel", "angry", "wrath", "streit", "zornig", "zorn"],
    "Battle": ["fought", "battle", "sword", "slew", "kämpfte", "schwert", "erschlug"],
    "Escape": ["fled", "escaped", "ran away", "floh", "entkam", "lief davon"],
    "Death": ["died", "dead", "killed", "starb", "tot", "getötet"],
    "Resurrection": ["came to life", "revived", "wieder lebendig", "erwachte"],
    "Marriage": ["married", "wedding", "bride", "heiratete", "hochzeit", "braut"],
    "Return": ["returned", "came home", "kehrte zurück", "kam heim"],
    "Reward": ["reward", "treasure", "riches", "belohnung", "schatz", "reichtum"],
    "Punishment": ["punished", "punishment", "bestraft", "strafe"],
}

#: 緊張度の語(高いほど張りつめている)。kokoro-graph 方式の自前辞書
TENSION_HIGH = [
    "death", "died", "kill", "killed", "blood", "fear", "afraid", "terror", "cried",
    "screamed", "danger", "fight", "fought", "sword", "wolf", "devil", "witch", "curse",
    "punish", "angry", "wrath", "flee", "fled", "escape", "monster", "giant", "dragon",
    "tod", "starb", "töten", "getötet", "blut", "angst", "fürchtete", "schrie", "gefahr",
    "kämpfte", "schwert", "teufel", "hexe", "fluch", "strafe", "zorn", "floh", "riese",
    "drache", "ungeheuer",
]
TENSION_LOW = [
    "happy", "happily", "peace", "peaceful", "joy", "rejoiced", "merry", "feast",
    "wedding", "married", "rest", "slept", "quiet", "gentle", "kind", "loved", "beautiful",
    "glücklich", "frieden", "freude", "freute", "fröhlich", "fest", "hochzeit", "heiratete",
    "ruhe", "schlief", "still", "sanft", "liebte", "schön",
]

#: テーマ(設計書 §12)。Embedding で当てるための説明文。**数え上げではない**
THEMES: dict[str, str] = {
    "家族": "a tale about family: parents and children, brothers and sisters, stepmothers",
    "旅": "a tale about setting out on a journey, travelling far, wandering the world",
    "成長": "a tale about a young person growing up, learning, coming of age",
    "勇気": "a tale about courage, a brave hero facing danger without fear",
    "善悪": "a tale about good and evil, the wicked punished and the good rewarded",
    "裏切り": "a tale about betrayal, deceit, a false friend or treacherous brother",
    "愛情": "a tale about love between a man and a woman, longing and devotion",
    "結婚": "a tale ending in a wedding, a bride and bridegroom, marriage to a king's child",
    "貧困": "a tale about poverty, hunger, a poor man with nothing to eat",
    "富": "a tale about riches, gold, treasure and becoming wealthy",
    "権力": "a tale about kings, rulers, power over others, a throne",
    "自然": "a tale about mountains, forests, rivers, the sea, wind and weather",
    "動物": "a tale in which animals speak and act like people",
    "魔法": "a tale about magic, spells, enchantment and wonders",
    "怪物": "a tale about a monster, giant, dragon or ogre that must be defeated",
    "死": "a tale about death, dying, and the dead",
    "再生": "a tale about coming back to life, revival, resurrection",
    "知恵": "a tale about cleverness, wit and outwitting a stronger opponent",
    "欲望": "a tale about greed, wanting more and more, never being satisfied",
    "禁忌": "a tale about a forbidden thing, a rule that must not be broken, a door not to open",
}

#: モチーフ(設計書 §11)。同じく Embedding で当てる
MOTIFS: dict[str, str] = {
    "特殊出生": "a child born in a strange or miraculous way, from a fruit, a wish or a spell",
    "旅立ち": "the hero leaves home to seek his fortune in the wide world",
    "試練": "the hero is given three difficult tasks that seem impossible",
    "助力者": "a helper appears — an old woman, an animal, a spirit — and gives aid",
    "怪物退治": "the hero fights and kills a monster, dragon, giant or ogre",
    "魔法の品": "a magic object: a ring, a cloth, a table, a purse that never empties",
    "変身": "a person is turned into an animal or object, and later turned back",
    "禁忌の破り": "someone breaks a prohibition — opens the forbidden door, looks back, speaks",
    "贈与": "a gift is given to the hero as reward for kindness",
    "結婚の成就": "the hero wins the hand of the princess and the wedding is held",
    "王位継承": "the hero becomes king, or inherits the kingdom",
    "財宝獲得": "gold and treasure are found and carried home",
    "復讐": "revenge is taken on those who wronged the hero",
    "契約": "a bargain or pact is made, often with the devil, with a price to pay",
    "死と埋葬": "someone dies and is buried, and the grave matters to the story",
    "再生": "the dead comes back to life, or bones are gathered and made whole",
}
