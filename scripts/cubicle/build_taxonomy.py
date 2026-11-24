"""Writes data/cubicle/taxonomy.json (19 sections) from the compact table below.

Node line format:  id | title | shelf(e/s/f) | level(b/i/a/x) | keywords (comma list) | practice (may be blank)
Keyword syntax (see classify.py): plain = whole word/phrase (plural tolerant), `stem*` = prefix match.
Blank practice -> the section default.  Lichess theme routes use the {TH} placeholder.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DATA_DIR, ROOT, dump_json  # noqa: E402

SH = {"e": "evergreen", "s": "semi", "f": "fast"}
TH = "#/train?tab=puzzles&set=themed&theme="
LESSON = "#/learn?l="

# (section id, title, blurb, floor, default practice, nodes)
S = [
("start", "Start here", "Zero to first games: the board, how pieces move, special moves, basic mates and opening habits.", 40, "#/learn", """
start-board|Board and pieces|e|b|chess board,set up the board,how to set up,chess pieces,piece values,board coordinates,files and ranks,algebraic|#/learn?l=board-setup
start-moves|How the pieces move|e|b|how to move,how pieces move,pawn moves,knight moves,bishop moves,rook moves,queen moves,king moves,how the knight,how the bishop,how the rook,how the queen,how the pawn|#/learn?l=rook-moves
start-special|Castling, en passant, promotion|e|b|castling,castle,en passant,promotion,promote,underpromotion,special moves|#/learn?l=castling
start-check|Check, checkmate, stalemate|e|b|checkmate,check and mate,stalemate,what is check,what is checkmate,draw by,threefold,fifty-move,insufficient material|#/learn?l=checkmate
start-notation|Notation|e|b|notation,algebraic notation,read a chess,write down,scoresheet,pgn|#/learn?l=notation
start-mates|Basic checkmates|e|b|queen and king,king and queen,rook and king,king and rook,basic checkmate,ladder mate,scholar's mate,scholars mate,fool's mate,mate in 1,mate in one,easy checkmate,checkmate patterns for beginners|#/learn?l=mate-king-queen
start-opening|Opening principles|e|b|opening principles,opening for beginners,beginner opening,how to start a chess game,first moves,control the center,develop your pieces,opening basics,opening rules|#/learn?l=opening-develop
start-mistakes|Common beginner mistakes|e|b|undefended pieces,undefended,beginner mistakes,common mistakes,mistakes beginners,stop blundering,hanging pieces,blunder,avoid these mistakes,mistakes you make|#/learn?l=blunder-check
start-zero|Learning chess from zero|e|b|chess fundamentals,fundamentals,learn chess,how to play chess,chess for beginners,beginner,beginners,chess basics,chess tutorial,chess rules,from scratch,absolute beginner,complete beginner,chess 101|#/learn
"""),
("tactics", "Tactics", "Forks, pins, mating patterns and the sacrifices that win games, plus how to train them.", 70, "#/train?tab=puzzles", """
tac-fork|Forks|e|b|fork,knight fork,royal fork,family fork,double attack|{TH}fork
tac-pin|Pins|e|b|pin,pins,pinned,absolute pin,relative pin|{TH}pin
tac-skewer|Skewers|e|i|skewer,x-ray,x ray|{TH}skewer
tac-discovered|Discovered attacks|e|i|discovered attack,discovered check,discovery,windmill|{TH}discoveredAttack
tac-deflection|Deflection and decoy|e|i|deflection,decoy,attraction,lure|{TH}deflection
tac-defender|Removing the defender|e|i|removing the defender,remove the defender,eliminate the defender,undermining,capturing the defender,destroy the defender|{TH}capturingDefender
tac-backrank|Back rank|e|b|back rank,back-rank,backrank,luft|{TH}backRankMate
tac-matepatterns|Mating patterns|e|i|mating pattern,mating patterns,mate patterns,checkmate patterns,smothered mate,arabian mate,anastasia,boden's mate,boden mate,epaulette,hook mate,dovetail,greco's mate,mate in 2,mate in 3,mate in two,mate in three,mating net,queen sacrifice mate|{TH}mate
tac-double|Double check|e|i|double check|{TH}doubleCheck
tac-zwischen|Zwischenzug|e|a|zwischenzug,intermezzo,in-between move,desperado|{TH}intermezzo
tac-trapped|Trapped pieces|e|i|trapped piece,trap the,trapped bishop,trapped knight,trapped queen,trapped rook,trap a piece|{TH}trappedPiece
tac-overload|Overloading|e|a|overload*,overworked,overworked defender|{TH}sacrifice
tac-perpetual|Perpetual and stalemate tricks|e|i|perpetual,perpetual check,stalemate trick,stalemate trap,swindle,fortress trick,draw trick,saving a lost|#/train?tab=puzzles
tac-sacs|Sacrifices|e|a|sacrific*,greek gift,exchange sac,piece sac,queen sac,rook sac,bishop sac,knight sac,brilliant sac,sac the|{TH}sacrifice
tac-drills|Pattern drills|e|i|tactics,tactical,puzzle rush,tactic training,tactics training,tactical patterns,tactical motifs,puzzle storm,chess tactics,combination|#/train?tab=puzzles
tac-method|Puzzle method|e|i|how to solve puzzles,solving puzzles,puzzle method,puzzle*,how to train tactics,tactics trainer,improve your tactics,tactical vision|#/train?tab=puzzles
"""),
("calc", "Calculation and thinking", "How to think: candidate moves, visualisation, blunder checks and managing the clock.", 20, "#/train?tab=challenges", """
calc-candidates|Candidate moves|e|i|candidate move,candidate moves,calculation,calculate,calculating,variations,analyze variations,look ahead|
calc-visual|Visualisation|e|i|visuali*,see the board,mental board,board vision|
calc-blindfold|Blindfold training|e|a|blindfold,blind chess,play blind|
calc-process|Thinking process|e|i|thinking process,think like,how to think,decision making,thought process,chess thinking,how grandmasters think,how gms think,improve your thinking,intuition,pattern recognition,how to analyse a position,how to analyze a position|
calc-blunder|Blunder checks|e|b|blunder check,blunder checking,checks captures threats,avoid blunders,double-check your move,safety check,oversight|#/learn?l=blunder-check
calc-time|Time management|e|i|time management,manage your time,clock management,time trouble,think too long,thinking time,use your time|#/learn?l=time-management
"""),
("strategy", "Strategy", "Pawn structure, weak squares, piece activity and the typical plans that grow from them.", 60, "#/learn", """
str-pawns|Pawn structure|e|i|pawn structure,pawn structures,pawn chain,isolated pawn,doubled pawn,backward pawn,passed pawn,pawn islands,pawn majority,hanging pawns|#/learn?l=pawn-structure
str-outposts|Outposts and weak squares|e|i|outpost,outposts,weak square,weak squares,weak colour,weak color,hole,holes|
str-files|Open files|e|i|open file,open files,rook activity,seventh rank,7th rank,rook on the seventh,half-open file,semi-open|#/learn?l=open-files
str-activity|Piece activity|e|i|piece activity,active pieces,activate your pieces,improve your worst piece,worst piece,piece coordination,piece placement|#/learn?l=piece-activity
str-bvn|Bishop vs knight|e|i|bishop vs knight,bishop versus knight,knight vs bishop,knight or bishop,bishop pair,two bishops,bishops or knights|
str-goodbad|Good and bad bishop|e|i|good bishop,bad bishop,bad bishops,good vs bad|
str-space|Space and the center|e|a|space advantage,gain space,cramp,restrict,central control,strong center,classical center,hypermodern|
str-prophy|Prophylaxis|e|a|prophylaxis,prophylactic,nimzowitsch,prevent the opponent,what does my opponent want|
str-imbalance|Imbalances|e|a|imbalance,imbalances,material imbalance,exchange sacrifice for,minor piece for,positional sacrifice|
str-breaks|Pawn breaks|e|a|pawn break,pawn breaks,pawn lever,pawn levers,break the center,c4-c5,f5 break,e5 break,d5 break|
str-initiative|Initiative and tempo|e|a|initiative,tempo,keeping the initiative,seize the initiative,dynamic play,dynamism|
str-convert|Converting an advantage|e|i|converting an advantage,convert an advantage,convert a winning,winning a won position,how to win a winning,trade down,simplify,how to win when ahead,winning technique,closing out|#/learn?l=trade-when-ahead
str-technique|Technique|e|a|technique,positional chess,positional play,positional,positional understanding,strategy,strategic,planning,make a plan,plans in chess,chess strategy|#/learn?l=make-a-plan
str-defence|Defence|e|a|defence,defense,defending,defend,defensive technique,passive position,fortress,resilience,swindling|
str-structures|Typical plans by structure|e|a|iqp,isolated queen's pawn,isolated queen pawn,carlsbad,maroczy,hedgehog,stonewall,benoni structure,french structure,slav structure,pawn structure and plans,typical plans,reversed sicilian|
"""),
("open-e4", "Openings as White: 1.e4", "Italian, Ruy Lopez, Scotch, Vienna and the open-game repertoire.", 20, "#/train?tab=openings", """
oe-italian|Italian Game|s|i|italian,italian game,giuoco piano,giuoco pianissimo,two knights defense,two knights defence,fried liver,max lange|
oe-ruy|Ruy Lopez|s|a|ruy lopez,spanish game,spanish opening,marshall attack,closed ruy,exchange ruy,anti-marshall,spanish torture|
oe-scotch|Scotch Game|s|i|scotch,scotch game,scotch gambit|
oe-vienna|Vienna Game|s|i|vienna,vienna game,vienna gambit|
oe-kg|King's Gambit|s|i|king's gambit,kings gambit,king gambit,falkbeer|
oe-evans|Evans Gambit|s|i|evans gambit,evans|
oe-fourknights|Four Knights and others|s|i|four knights,three knights,bishop's opening,center game,ponziani,philidor defence,philidor defense|
"""),
("open-d4", "Openings as White: 1.d4", "London, Queen's Gambit, Catalan and the queen-pawn systems.", 20, "#/train?tab=openings", """
od-london|London System|s|b|london system,london,the london|
od-qg|Queen's Gambit|s|i|queen's gambit,queens gambit,qgd,qga,queen's gambit accepted,queen's gambit declined|
od-catalan|Catalan|s|a|catalan|
od-colle|Colle System|s|b|colle,colle system,colle-zukertort,zukertort|
od-tromp|Trompowsky|s|i|trompowsky,tromp,tromp attack|
od-jobava|Jobava London|s|i|jobava,jobava london|
od-torre|Torre Attack|s|b|torre,torre attack|
"""),
("open-flank", "Openings: flank and system", "English, Reti, Bird and king's-indian-attack setups.", 20, "#/train?tab=openings", """
of-english|English Opening|s|a|english opening,english,1.c4,c4 opening,symmetrical english,botvinnik system|
of-reti|Reti Opening|s|i|reti,reti opening,1.nf3,nf3 opening,zukertort opening|
of-bird|Bird Opening|s|i|bird opening,bird's opening,birds opening,from's gambit|
of-kia|King's Indian Attack|s|i|king's indian attack,kings indian attack,kia,barcza,sokolsky,orangutan|
"""),
("def-e4", "Defences to 1.e4", "Sicilian, French, Caro-Kann and the rest of Black's answers.", 20, "#/train?tab=openings", """
de-najdorf|Sicilian: Najdorf|s|a|najdorf|
de-dragon|Sicilian: Dragon|s|a|dragon,sicilian dragon,yugoslav attack|
de-sveshnikov|Sicilian: Sveshnikov|s|a|sveshnikov,chelyabinsk|
de-taimanov|Sicilian: Taimanov and Kan|s|a|taimanov,kan sicilian,paulsen,scheveningen|
de-alapin|Sicilian: Alapin|s|i|alapin,c3 sicilian,2.c3|
de-accdragon|Accelerated Dragon|s|a|accelerated dragon|
de-sicilian|Sicilian: general|s|i|sicilian,sicilian defense,sicilian defence,open sicilian,closed sicilian,grand prix attack,smith-morra|
de-french|French Defence|s|i|french defense,french defence,french,advance french,winawer,tarrasch french,exchange french|
de-caro|Caro-Kann|s|i|caro-kann,caro kann,caro|
de-pirc|Pirc and Modern|s|i|pirc,modern defense,modern defence,austrian attack|
de-scandi|Scandinavian|s|b|scandinavian,center counter,centre counter|
de-alekhine|Alekhine Defence|s|a|alekhine's defense,alekhine's defence,alekhine defense,alekhine defence|
de-e5|1...e5 mainlines|s|a|petroff,petrov,berlin,berlin defense,berlin defence,berlin wall,1...e5,open games,italian defense|
"""),
("def-d4", "Defences to 1.d4", "QGD, Slav, King's Indian, Grunfeld, Nimzo and the other ways to meet queen-pawn openings.", 20, "#/train?tab=openings", """
dd-qgd|Queen's Gambit Declined|s|i|queen's gambit declined,qgd,orthodox defense,tartakower,lasker defense|
dd-slav|Slav|s|i|slav,slav defense,slav defence,chebanenko|
dd-semislav|Semi-Slav|s|a|semi-slav,semi slav,meran,botvinnik semi|
dd-kid|King's Indian|s|a|king's indian,kings indian,kid,saemisch,sämisch,four pawns attack,mar del plata|
dd-grunfeld|Grunfeld|s|a|grunfeld,grünfeld|
dd-nimzo|Nimzo-Indian|s|a|nimzo,nimzo-indian,nimzo indian,nimzoindian|
dd-qid|Queen's Indian|s|a|queen's indian,queens indian,qid,bogo-indian,bogo indian|
dd-benoni|Benoni|s|a|benoni,modern benoni,czech benoni|
dd-dutch|Dutch Defence|s|i|dutch,dutch defense,dutch defence,stonewall dutch,leningrad dutch|
dd-benko|Benko Gambit|s|a|benko,volga gambit|
dd-budapest|Budapest Gambit|s|i|budapest,budapest gambit|
"""),
("gambits", "Gambits and traps", "Danish, Smith-Morra, Englund and other sharp, trappy lines.", 20, "#/train?tab=openings", """
gam-danish|Danish Gambit|s|i|danish gambit,danish|
gam-morra|Smith-Morra Gambit|s|i|smith-morra,smith morra,morra gambit,morra|
gam-englund|Englund Gambit|s|b|englund,englund gambit|
gam-stafford|Stafford Gambit|s|b|stafford,stafford gambit|
gam-bdg|Blackmar-Diemer Gambit|s|i|blackmar-diemer,blackmar diemer,bdg,blackmar|
gam-latvian|Latvian and others|s|i|latvian,latvian gambit,albin,elephant gambit,halloween gambit,jerome gambit,wing gambit,from gambit,gambit,opening trap,opening traps,trap,traps,trappy|
"""),
("open-study", "Opening study", "How to study openings, build a repertoire and use engines and databases.", 20, "#/train?tab=openings", """
os-how|How to study openings|e|i|how to study openings,study openings,learn openings,learning openings,how to learn openings,memorize openings,memorise openings,opening preparation,opening theory,opening study|
os-rep|Building a repertoire|s|i|ideas for black,ideas for white,queen pawn,repertoire,build a repertoire,opening repertoire,which opening,best openings,openings for beginners,openings to learn,choose an opening,opening choice|
os-trans|Transpositions|s|a|transposition,transpositions,transpose,move order,move orders|
os-engine|Engines and databases|s|a|engine,databases,database,stockfish,opening explorer,lichess opening,chessbase,opening tree,novelty,theory novelty|
os-mistakes|Opening mistakes by rating|e|b|opening mistakes,opening blunders,mistakes in the opening,opening errors,common opening,bad openings,opening traps to avoid|
"""),
("middlegame", "Middlegame", "Attacking the king, pawn storms, defending and finding plans.", 20, "#/learn", """
mg-attack|Attacking the king|e|i|attack*,attacking the king,king attack,kingside attack,king hunt,attacking chess,attacking play,attacking patterns,mating attack|
mg-storm|Pawn storms|e|a|pawn storm,pawn storms,pawn advance,g4,h4 push,pawn push|
mg-oppcastle|Opposite-side castling|e|a|opposite side castling,opposite-side castling,opposite castling,opposite sides|
mg-defend|Defending|e|a|defending against,how to defend,defend against,counterattack,counter-attack,counterplay,survive,defensive|
mg-plans|Plans and initiative|e|a|middlegame,middle game,plans,find a plan,strategic plan,initiative,transition|
"""),
("endgames", "Endgames", "Pawn, rook, minor-piece and queen endings, plus practical technique.", 60, "#/train?tab=endgames", """
end-pawn|Pawn endings|e|b|pawn ending,pawn endings,pawn endgame,king and pawn,opposition,triangulation,square rule,rule of the square,key squares,outside passed pawn,zugzwang|
end-rook|Rook endings|e|i|rook ending,rook endings,rook endgame,rook endgames,lucena,philidor position,vancura,cutting off the king,bridge building,rook and pawn,rook vs pawn,tarrasch rule,active rook|
end-minor|Minor piece endings|e|i|bishop endgame,knight endgame,bishop vs knight endgame,same colored bishops,same-colored bishops,opposite colored bishops,opposite-colored bishops,opposite colour bishops,opposite bishops,wrong bishop,minor piece ending|
end-queen|Queen endings|e|a|queen ending,queen endings,queen endgame,queen vs pawn,queen versus rook,queen and pawn|
end-practical|Practical endgames|e|i|endgame,endgames,end game,endings,endgame technique,endgame tips,endgame principles,endgame basics,must know endgames,essential endgames|
end-technical|Technical endgames|e|a|technical endgame,theoretical endgame,tablebase,tablebases,syzygy,endgame theory,endgame study,endgame studies,composition|
"""),
("analysis", "Game analysis", "Annotated classics, engine-era games and how to review your own.", 50, "#/learn", """
an-classic|Classic annotated games|e|i|morphy,immortal game,evergreen game,opera game,capablanca,lasker,tal,fischer,botvinnik,karpov,kasparov,spassky,petrosian,steinitz,anderssen,game of the century,classic game,legendary game|
an-engine|Engine-era top games|s|a|alphazero,stockfish vs,leela,lc0,neural net,deepmind,engine game,computer game,super grandmaster game,candidates game,world championship game,carlsen vs,nakamura vs,caruana vs,firouzja vs,gukesh vs,ding vs,nepomniachtchi vs,ding liren|
an-modern|Modern masterpieces|s|i|masterpiece,brilliant game,brilliancy,best game,incredible game,unbelievable game,crazy game,amazing game,beautiful game,game of the year,greatest game,best move|
an-review|GM reviews of club games|s|b|review,reviews your games,reviewing,reviewing your,game review,subscriber game,viewer game,analyzing your games,analysing your games,analysis of your game,under 1000,under 1500|
an-guess|Guess the move and Elo|s|i|guess the move,guess the elo,guess the rating,guess the opening,find the best move,what would you play,spot the|
an-own|Reviewing your own games|e|i|analyze your own games,analyse your own games,review your own games,how to analyze,how to analyse,how to review,game analysis,post-game analysis,improve by analysing,annotate|
"""),
("gameplay", "Gameplay", "Games played with the thought process spoken aloud.", 50, "#/train?tab=challenges", """
gp-blitz|Blitz commentary|s|i|blitz,3+0,3 minute,5 minute,3+2,blitz game,blitz chess,blitz battle|
gp-rapid|Rapid commentary|s|i|rapid,10+0,15+10,rapid game,rapid chess|
gp-bullet|Bullet and speedruns|s|a|bullet,1+0,speedrun,speed run,hyperbullet,1 minute,ultrabullet|
gp-stream|Titled streamers|s|a|stream,streamer,live stream,titled tuesday,pogchamps,pog champs,vs viewers,chess session|
gp-brilliancy|Brilliancy walkthroughs|e|i|brilliancy,brilliancies,walkthrough,i played,my game,my best game,sacrificed,sacrifice my queen,sacrificing my queen|
gp-960|Chess960|s|i|chess960,chess 960,fischer random,freestyle chess,freestyle,960|
"""),
("news", "Tournaments and news", "Round recaps and highlights from the big events.", 20, "#/learn", """
nw-wch|World Championship|f|i|world championship,world chess championship,wcc,ding vs gukesh,gukesh vs ding|
nw-cand|Candidates|f|a|candidates,candidates tournament,fide candidates|
nw-olympiad|Olympiad|f|i|olympiad,chess olympiad,fide olympiad,team event,team championship|
nw-tata|Tata Steel|f|i|tata steel,wijk aan zee,tata steel chess|
nw-norway|Norway Chess|f|i|norway chess,armageddon,stavanger|
nw-gct|Grand Chess Tour|f|i|grand chess tour,gct,sinquefield cup,superbet,saint louis rapid,st. louis rapid,paris rapid,tour final|
nw-wc|World Cup and others|f|i|total chess,semifinal,finals,clutch chess,crowned,tournament,drama,forfeit,hans niemann,world cup,fide world cup,grand swiss,fide grand swiss,world rapid,world blitz,highlights,round,day 1,day 2,day 3,recap,commentary,live commentary,live coverage,speed chess championship,champions chess tour,esports world cup,rapid and blitz championship|
"""),
("improve", "Improve", "Training methods by rating band, psychology and study plans.", 40, "#/learn", """
imp-b|Under 1000|e|b|under 1000,below 1000,0-1000,beginner to 1000,from 400,from 600,from 800,0 to 1000,sub 1000|#/learn?l=practice-routine
imp-i|1000 to 1500|e|i|1000-1500,1000 to 1500,1200,1300,1400,1500,beginner to intermediate,intermediate player,intermediate players|
imp-a|1500 to 2000|e|a|1500-2000,1500 to 2000,1600,1700,1800,1900,2000 elo,club player,club players,advanced player|
imp-x|2000 and above|e|x|2000+,2000-2500,2200,2300,2400,master level,become a master,become an im,become a gm,titled player,from 2000,above 2000|
imp-plateau|Plateaus|e|i|plateau,plateaus,stuck at,stuck in,break through,why you are not improving,why you aren't improving,why you're stuck,not improving,get unstuck|
imp-mind|Tilt and psychology|e|i|tilt,psychology,mindset,nerves,confidence,mental,losing streak,rage,focus,fear of losing,motivation|
imp-time|Time management|e|i|time management in chess,manage the clock,clock,time pressure|#/learn?l=time-management
imp-otb|OTB tournament prep|s|i|otb,over the board,over-the-board,tournament prep,tournament preparation,play a tournament,first tournament,classical game,fide rating|
imp-online|Online vs OTB|s|i|online vs otb,online versus otb,online chess vs,transition to otb|
imp-lichess|Lichess and engines|s|i|lichess,lichess tips,use stockfish,analysis board,lichess features,engine analysis,lichess study,lichess tutorial|
imp-plan|Study plans|e|i|study plan,training plan,improve at chess,improve your chess,get better at chess,how to improve,how to get better,improve fast,rating climb,climb,climbing,get to 1500,get to 2000,training routine,daily routine,practice routine,chess improvement|#/learn?l=practice-routine
"""),
("speed", "Speed chess", "Blitz, bullet and rapid strategy, premoves and flagging.", 20, "#/train?tab=challenges", """
sp-blitz|Blitz strategy|s|i|blitz strategy,blitz tips,win at blitz,how to win blitz,blitz openings,improve at blitz,play blitz,blitz rating|
sp-bullet|Bullet strategy|s|i|bullet strategy,bullet tips,win at bullet,how to win bullet,bullet chess,improve at bullet,bullet rating|
sp-rapid|Rapid strategy|s|i|rapid strategy,rapid tips,win at rapid,rapid rating|
sp-pre|Premoves|s|i|premove,premoves,pre-move,pre move,mouse slip,mouse skills,mousework|
sp-flag|Flagging and time scrambles|s|a|flag,flagging,time scramble,scramble,increment,low on time,win on time,time odds,clock tricks|
"""),
("legends", "Legends and stories", "Documentaries, famous matches, history and interviews.", 20, "#/learn", """
lg-docs|Player documentaries|e|i|documentary,biography,life story,rise and fall,story of,the story,his life,her life,career,the genius,the legend,the prodigy|
lg-matches|Famous matches|e|i|fischer vs spassky,fischer-spassky,kasparov vs deep blue,deep blue,carlsen vs nepomniachtchi,match of the century,karpov vs kasparov,kasparov vs karpov,century match|
lg-history|History|e|i|history of chess,chess history,origin of chess,evolution of chess,chaturanga,the turk,mechanical turk,chess in the soviet,soviet chess,hall of fame|
lg-interviews|Interviews|s|i|interview,interviews,q&a,ama,sits down with,conversation with,talks with,podcast,press conference|
"""),
]


def build():
    sections = []
    nodes_total = 0
    lessons = {p.stem for p in (ROOT / "data" / "lessons").glob("*.json")}
    for sid, title, blurb, floor, dflt, body in S:
        nodes = []
        for line in body.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) != 6:
                raise SystemExit(f"bad node line (need 6 fields): {line[:60]}")
            nid, ntitle, shelf, level, kws, prac = parts
            prac = prac.replace("{TH}", TH)
            if prac.startswith(LESSON) and prac[len(LESSON):] not in lessons:
                raise SystemExit(f"practice lesson missing: {prac}")
            keywords = [k.strip().lower() for k in kws.split(",") if k.strip()]
            nodes.append({"id": nid, "title": ntitle, "shelf": SH[shelf], "level": level,
                          "keywords": keywords, "practice": prac or dflt})
        nodes_total += len(nodes)
        sections.append({"id": sid, "title": title, "blurb": blurb, "floor": floor, "nodes": nodes})
    return sections, nodes_total


def main():
    sections, n = build()
    ids = [x["id"] for s in sections for x in s["nodes"]]
    assert len(ids) == len(set(ids)), "duplicate node ids"
    dump_json(DATA_DIR / "taxonomy.json", {"sections": sections})
    print(f"taxonomy: {len(sections)} sections, {n} nodes")


if __name__ == "__main__":
    main()
