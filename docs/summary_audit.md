# LLM column-summary audit

Random sample of 20 of 798 columns (seed 7). Each long summary is graded against the profile it was generated from.

Grades: **OK** = every claim is supported. **MINOR** = imprecise or misattributed, but nothing false about the data. **WRONG** = contains a false statement; its SQL impact is noted.

Graded by the assistant (Claude) against the profile text, plus domain knowledge where noted. Owner review recommended.

## Result

| Grade | Count | |
|---|---|---|
| OK | 12 / 20 (60%) | |
| MINOR | 4 / 20 (20%) | misattributed examples, vague wording |
| WRONG | 4 / 20 (20%) | 1 copied number; **3 wrong *meanings* of cryptic codes** (X/Y formation coordinates, `UG`) |

**Takeaway:** Profiling is reliable for **formats and literals**: exact case, date patterns, storage types, multi-value strings. It is unreliable for the **meaning** of cryptic names and codes, where only an SME knows the answer. That is the paper's argument for *fused* metadata (C3): profiles supply formats, and SME descriptions supply meanings. A 95% Wilson interval on a 20% error rate with n=20 is roughly 8–42%, so this is a qualitative signal, not a precise rate.

## 1. `european_football_2.Player_Attributes.standing_tackle`

**Profile:** Column standing_tackle has 836 NULL values out of 183978 records. There are 95 distinct values. The minimum value is '1' and the maximum value is '95'. Most common non-NULL column values (with counts) are '25' (11090), '68' (4913), '66' (4861), '65' (4608), '67' (4595), '72' (4433), '71' (4249), '69' (4206), '64' (4176), '74' (4136). Value lengths range from 1 to 2 characters. Every column value looks like a number. Values are stored as INTEGER.

**Short:** The standing_tackle column stores an integer representing a player's standing tackle rating, containing 95 distinct values ranging from 1 to 95 with many NULLs.

**Long:** This INTEGER column holds standing tackle ratings as numeric literals like '25', '68', or '66'. It contains 83,600 NULL values out of 183,978 records. Values range from 1 to 95 and are stored strictly as integers, not text.

**Grade:** **WRONG**: says 83,600 NULLs; the profile says 836 (a digit-copy error). Low SQL impact.

## 2. `card_games.cards.supertypes`

**Profile:** Column supertypes has 48982 NULL values out of 56822 records. There are 8 distinct values. The minimum value is 'Basic' and the maximum value is 'World'. Most common non-NULL column values (with counts) are 'Legendary' (4286), 'Basic' (3269), 'Snow' (142), 'World' (47), 'Basic,Snow' (35), 'Host' (28), 'Legendary,Snow' (21), 'Ongoing' (12). Value lengths range from 4 to 14 characters. Values are stored as TEXT.

**Short:** The supertypes column stores a comma-separated TEXT string of zero to multiple Magic: The Gathering card supertype designations, or NULL.

**Long:** This TEXT column holds comma-separated supertype values such as 'Legendary', 'Basic', 'Snow', 'World', 'Host', or combinations like 'Basic,Snow' and 'Legendary,Snow'. It contains 48,982 NULLs out of 56,822 records. Values range from 4 to 14 characters; analysts must handle potential multiple values per row via string splitting.

**Grade:** **OK**: correctly infers comma-separated multi-values, which is useful for `LIKE` predicates.

## 3. `european_football_2.Match.away_player_X3`

**Profile:** Column away_player_X3 has 1832 NULL values out of 25979 records. There are 8 distinct values. The minimum value is '2' and the maximum value is '9'. Most common non-NULL column values (with counts) are '4' (22465), '5' (967), '3' (331), '6' (271), '8' (65), '2' (34), '7' (13), '9' (1). The values are always 1 characters long. Every column value looks like a number. Values are stored as INTEGER.

**Short:** away_player_X3 stores an integer representing a specific player's jersey number or identifier for the away team, containing values between 2 and 9.

**Long:** This INTEGER column likely represents a player identifier (e.g., jersey number) for the away team, with valid non-NULL values ranging from '2' to '9'. It is highly sparse, containing 1832 NULLs out of 25979 records, where '4' is the dominant value (22465 occurrences). Values are stored as integers despite being single-digit numbers.

**Grade:** **WRONG**: guesses 'player identifier (jersey number)' and 'highly sparse' (7% NULL). In this dataset, X/Y columns are pitch-formation coordinates. The guess is hedged with 'likely', but still false.

## 4. `student_club.budget.remaining`

**Profile:** Column remaining has 0 NULL values out of 52 records. There are 22 distinct values. The minimum value is '-24.25' and the maximum value is '150.0'. Most common non-NULL column values (with counts) are '150.0' (8), '75.0' (4), '55.0' (4), '25.0' (4), '20.0' (4), '10.0' (4), '4.0' (3), '0.75' (3), '-0.199999999999999' (3), '11.55' (2). Value lengths range from 3 to 18 characters. Every column value looks like a number. Values are stored as REAL.

**Short:** The 'remaining' column stores numeric REAL values representing budget balance, containing no NULLs and ranging from -24.25 to 150.0.

**Long:** This REAL column holds exact numeric literals such as '-24.25', '150.0', and '-0.199999999999999' with no NULL values across 52 records. Values range from -24.25 to 150.0, stored as floating-point numbers where some entries exhibit precision artifacts like '-0.199999999999999'. No sentinel codes or text formats exist.

**Grade:** **OK**: notes the floating-point artifact (`-0.199999999999999`), which matters for equality predicates.

## 5. `california_schools.schools.City`

**Profile:** Column City has 293 NULL values out of 17686 records. There are 1165 distinct values. The minimum value is 'Acampo' and the maximum value is 'Zenia'. Most common non-NULL column values (with counts) are 'Los Angeles' (837), 'San Diego' (427), 'San Jose' (407), 'Sacramento' (334), 'Fresno' (277), 'Oakland' (254), 'San Francisco' (253), 'Bakersfield' (203), 'Stockton' (198), 'Riverside' (122). Value lengths range from 3 to 25 characters. Values are stored as TEXT.

**Short:** The City column stores the city name of a school as a TEXT string, containing 1165 distinct values ranging from 3 to 25 characters.

**Long:** This TEXT column holds the city name for each school record, with common examples including 'Los Angeles', 'San Diego', and 'Acampo'. It contains 293 NULL values out of 17,686 total records and no sentinel codes.

**Grade:** **MINOR**: lists 'Acampo' as a common value; it is only the alphabetical minimum.

## 6. `california_schools.schools.GSserved`

**Profile:** Column GSserved has 5743 NULL values out of 17686 records. There are 81 distinct values. The minimum value is '1' and the maximum value is 'K-9'. Most common non-NULL column values (with counts) are 'K-5' (2688), 'K-6' (2221), '9-12' (1672), 'K-8' (1024), '6-8' (1019), '7-8' (433), '10-12' (335), 'K-12' (330), '7-12' (246), '11-12' (156). Value lengths range from 1 to 5 characters. Values are stored as TEXT. Value formats (9 = digit, A/a = letter) are '9-9' (38%), '9-99' (27%), 'A-9' (11%).

**Short:** GSserved is a TEXT column indicating the grade levels served by a school, containing values like 'K-5' or '9-12', with 5743 NULLs out of 17686 records.

**Long:** GSserved stores grade ranges as TEXT in formats like '9-9' (e.g., '1-9'), '9-99' (e.g., 'K-9'), or 'A-9' (e.g., 'K-5'). It contains 81 distinct values with common examples including 'K-5', '6-8', and '9-12'. The column has 5743 NULLs, and all non-null values are strings representing grade spans.

**Grade:** **MINOR**: maps formats to the wrong examples ('9-99' e.g. 'K-9'). The literals themselves are real.

## 7. `financial.trans.bank`

**Profile:** Column bank has 782812 NULL values out of 1056320 records. There are 13 distinct values. The minimum value is 'AB' and the maximum value is 'YZ'. Most common non-NULL column values (with counts) are 'QR' (22285), 'AB' (21720), 'ST' (21711), 'YZ' (21582), 'GH' (21499), 'EF' (21293), 'KL' (21234), 'UV' (21167), 'OP' (21094), 'IJ' (20525). The values are always 2 characters long. Values are stored as TEXT. Value formats (9 = digit, A/a = letter) are 'AA' (100%).

**Short:** The 'bank' column stores 2-character text codes representing bank identifiers, with most values being two-letter alphabetic combinations.

**Long:** This TEXT column holds exactly 2-character alphabetic codes (e.g., 'QR', 'AB') representing bank identifiers. It contains 782,812 NULLs out of 1,056,320 records and features 13 distinct values ranging from 'AB' to 'YZ'. All non-null entries are strictly two-letter formats with no digits.

**Grade:** **OK**

## 8. `card_games.cards.colorIdentity`

**Profile:** Column colorIdentity has 6224 NULL values out of 56822 records. There are 31 distinct values. The minimum value is 'B' and the maximum value is 'W'. Most common non-NULL column values (with counts) are 'G' (8802), 'B' (8565), 'R' (8485), 'U' (8375), 'W' (8327), 'G,W' (784), 'G,R' (752), 'B,R' (733), 'B,U' (724), 'U,W' (722). Value lengths range from 1 to 9 characters. Values are stored as TEXT. Value formats (9 = digit, A/a = letter) are 'A,A' (32%), 'A,A,A' (32%), 'A' (16%).

**Short:** The colorIdentity column stores a comma-separated string of single-letter mana colors (e.g., 'G', 'B,R') representing a card's color identity, with 6224 NULL values out of 56822 records.

**Long:** This TEXT column holds comma-separated strings of single-letter mana colors like 'G', 'B', or 'G,W'. It contains 6224 NULLs among 56822 rows, with 31 distinct values ranging from length 1 to 9. Common non-NULL examples include 'G' (8802), 'B,R' (733), and 'A,A' formats representing up to nine colors.

**Grade:** **MINOR**: 'up to nine colors' confuses length (9 chars) with count. It also leaks the pattern notation ('A,A formats').

## 9. `european_football_2.Team_Attributes.defencePressureClass`

**Profile:** Column defencePressureClass has 0 NULL values out of 1458 records. There are 3 distinct values. The minimum value is 'Deep' and the maximum value is 'Medium'. Most common non-NULL column values (with counts) are 'Medium' (1243), 'Deep' (154), 'High' (61). Value lengths range from 4 to 6 characters. Values are stored as TEXT.

**Short:** defencePressureClass is a TEXT column containing one of three categorical values ('Deep', 'Medium', or 'High') representing defensive pressure intensity, with no NULLs.

**Long:** This TEXT column stores the defensive pressure class with no NULL values across 1458 records. It contains exactly three distinct literals: 'Deep' (154 occurrences), 'Medium' (1243 occurrences), and 'High' (61 occurrences). Values are case-sensitive strings ranging from 4 to 6 characters, where 'Medium' is the dominant value.

**Grade:** **OK**: all three literals with exact case.

## 10. `formula_1.driverStandings.raceId`

**Profile:** Column raceId has 0 NULL values out of 31578 records. There are 970 distinct values. The minimum value is '1' and the maximum value is '982'. Most common non-NULL column values (with counts) are '816' (108), '824' (105), '815' (103), '823' (100), '814' (98), '807' (97), '822' (96), '806' (95), '805' (94), '804' (93). Value lengths range from 1 to 3 characters. Every column value looks like a number. Values are stored as INTEGER.

**Short:** The raceId column is an INTEGER representing unique race identifiers ranging from 1 to 982, with no NULL values.

**Long:** This INTEGER column stores unique race identifiers ranging from '1' to '982' across 31,578 records. It contains no NULL values and holds 970 distinct values. Most frequent values include '816', '824', and '815'. All values are stored as numeric integers.

**Grade:** **MINOR**: 'unique race identifiers' could suggest the column is unique here (970 distinct values in 31,578 rows; it is a foreign key).

## 11. `california_schools.schools.Website`

**Profile:** Column Website has 10722 NULL values out of 17686 records. There are 4082 distinct values. The minimum value is 'acornstooakscharter.org' and the maximum value is 'www.yumingschool.org'. Most common non-NULL column values (with counts) are 'www.fusd.net' (49), 'www.pusd.org' (46), 'www.vusd.org' (42), 'www.compton.k12.ca.us' (41), 'www.fcusd.org' (38), 'www.dsusd.us' (36), 'www.nmusd.us' (35), 'www.aspirepublicschools.org' (34), 'www.mantecausd.net' (32), 'www.fsusd.org' (32). Value lengths range from 9 to 96 characters. Values are stored as TEXT.

**Short:** The Website column stores school website URLs as TEXT values, though it contains a high volume of NULLs.

**Long:** This TEXT column holds school website addresses, with examples like 'acornstooakscharter.org' and 'www.yumingschool.org'. It has 10722 NULL values out of 17686 records. Common non-NULL entries include 'www.fusd.net', 'www.pusd.org', and 'www.vusd.org'. Values range from 9 to 96 characters in length.

**Grade:** **OK**

## 12. `financial.district.A9`

**Profile:** Column A9 has 0 NULL values out of 77 records. There are 11 distinct values. The minimum value is '1' and the maximum value is '11'. Most common non-NULL column values (with counts) are '6' (14), '4' (12), '7' (11), '5' (10), '10' (7), '9' (7), '8' (7), '1' (4), '11' (2), '3' (2). Value lengths range from 1 to 2 characters. Every column value looks like a number. Values are stored as INTEGER.

**Short:** Column A9 is an INTEGER representing a numeric code ranging from 1 to 11, stored as whole numbers without NULLs.

**Long:** Column A9 is an INTEGER storing numeric codes between '1' and '11'. It contains no NULL values across 77 records. Most frequent values include '6', '4', and '7'. All values are stored as integers, not text.

**Grade:** **OK**: 'numeric codes' is vague, but honest. Without SME metadata, the meaning of `A9` is unknowable from values alone.

## 13. `codebase_community.postHistory.CreationDate`

**Profile:** Column CreationDate has 0 NULL values out of 303155 records. There are 189959 distinct values. The minimum value is '2009-02-02 14:21:12.0' and the maximum value is '2014-09-14 02:54:13.0'. Most common non-NULL column values (with counts) are '2012-02-22 19:46:04.0' (81), '2012-02-22 19:46:03.0' (46), '2012-02-22 19:46:05.0' (39), '2012-02-23 19:55:21.0' (20), '2010-08-01 18:56:25.0' (15), '2010-08-16 13:01:42.0' (14), '2011-06-01 03:42:00.0' (12), '2014-06-16 18:42:37.0' (11), '2012-08-21 15:17:25.0' (10), '2011-02-06 11:01:16.0' (10). The values are always 21 characters long. Values are stored as TEXT. Value formats (9 = digit, A/a = letter) are '9999-99-99 99:99:99.9' (100%).

**Short:** CreationDate is a DATETIME column storing the exact timestamp of post history events as 21-character text strings in 'YYYY-MM-DD HH:MM:SS.S' format.

**Long:** This column stores the creation timestamp for post history records. Values are stored as TEXT with a fixed 21-character length, strictly following the format '9999-99-99 99:99:99.9'. Examples include '2009-02-02 14:21:12.0' and '2014-09-14 02:54:13.0'. There are no NULL values, and all entries contain valid datetime literals.

**Grade:** **OK**: exact timestamp format, including the `.0` suffix.

## 14. `california_schools.satscores.AvgScrWrite`

**Profile:** Column AvgScrWrite has 596 NULL values out of 2269 records. There are 267 distinct values. The minimum value is '312' and the maximum value is '671'. Most common non-NULL column values (with counts) are '489' (20), '442' (20), '468' (19), '449' (18), '425' (18), '487' (17), '476' (17), '474' (17), '446' (17), '432' (17). The values are always 3 characters long. Every column value looks like a number. Values are stored as INTEGER.

**Short:** AvgScrWrite stores the average writing score as a 3-character integer string (e.g., '312' to '671'), with many NULL values.

**Long:** This column holds the average writing score as an INTEGER, though values are always formatted as exactly 3 characters like '312' or '671'. It contains 596 NULLs out of 2269 records. Common values include '489', '442', and '468'. No sentinel values exist; all non-NULL entries are numeric scores.

**Grade:** **OK**

## 15. `california_schools.schools.LastUpdate`

**Profile:** Column LastUpdate has 0 NULL values out of 17686 records. There are 757 distinct values. The minimum value is '1999-06-24' and the maximum value is '2016-10-12'. Most common non-NULL column values (with counts) are '2015-06-18' (4455), '1999-06-24' (3201), '2013-07-02' (555), '2009-01-30' (504), '2016-03-03' (387), '2015-06-23' (355), '2009-10-02' (248), '2016-07-19' (199), '2016-08-23' (197), '2016-07-01' (162). The values are always 10 characters long. Values are stored as TEXT. Value formats (9 = digit, A/a = letter) are '9999-99-99' (100%).

**Short:** LastUpdate stores the date of the last data modification as a 10-character text string in 'YYYY-MM-DD' format.

**Long:** This DATE column records the last update timestamp for school records, stored as TEXT with a fixed 10-character length. Values strictly follow the '9999-99-99' pattern (e.g., '2015-06-18', '1999-06-24'). It contains no NULL values and ranges from '1999-06-24' to '2016-10-12'. No sentinel or placeholder values are present.

**Grade:** **OK**

## 16. `european_football_2.Match.home_player_10`

**Profile:** Column home_player_10 has 1436 NULL values out of 25979 records. There are 3642 distinct values. The minimum value is '2625' and the maximum value is '742405'. Most common non-NULL column values (with counts) are '107417' (85), '24383' (84), '35724' (76), '30981' (67), '40636' (62), '30893' (60), '24448' (59), '184138' (58), '106474' (58), '178812' (57). Value lengths range from 4 to 6 characters. Every column value looks like a number. Values are stored as INTEGER.

**Short:** home_player_10 stores the unique numeric ID of the 10th player in the home team's starting lineup as an INTEGER.

**Long:** This column holds the unique integer ID for the 10th home player, stored as INTEGER with values ranging from '2625' to '742405'. It contains 3642 distinct IDs among 25979 records, with 1436 NULLs indicating missing lineup data. Common values include '107417', '24383', and '35724'.

**Grade:** **OK**

## 17. `european_football_2.Match.away_player_Y5`

**Profile:** Column away_player_Y5 has 1832 NULL values out of 25979 records. There are 5 distinct values. The minimum value is '3' and the maximum value is '9'. Most common non-NULL column values (with counts) are '3' (22645), '7' (1448), '5' (38), '6' (15), '9' (1). The values are always 1 characters long. Every column value looks like a number. Values are stored as INTEGER.

**Short:** away_player_Y5 stores an integer representing a specific player identifier (likely jersey number) for the away team, containing values between 3 and 9.

**Long:** This INTEGER column holds player identifiers for the away team, with valid non-NULL values strictly limited to single-digit integers '3', '7', '5', '6', or '9'. Approximately 1832 records contain NULLs. Values are stored as integers, not text.

**Grade:** **WRONG**: same coordinate-vs-identifier confusion as #3.

## 18. `california_schools.schools.EILCode`

**Profile:** Column EILCode has 1369 NULL values out of 17686 records. There are 7 distinct values. The minimum value is 'A' and the maximum value is 'UG'. Most common non-NULL column values (with counts) are 'ELEM' (7298), 'HS' (3367), 'UG' (2525), 'INTMIDJR' (1845), 'ELEMHIGH' (774), 'A' (352), 'PS' (156). Value lengths range from 1 to 8 characters. Values are stored as TEXT.

**Short:** EILCode is a TEXT column containing 7 distinct educational level codes (e.g., 'ELEM', 'HS') with 1369 NULL values.

**Long:** This TEXT column stores 7 distinct educational level codes ranging from 1 to 8 characters, including common literals like 'ELEM' (elementary), 'HS' (high school), and 'UG' (undergraduate). It contains 1369 NULL values out of 17686 records, requiring explicit handling in queries.

**Grade:** **WRONG**: expands 'UG' as 'undergraduate'. In California school codes, UG means *ungraded*. That could mislead a question about grade levels.

## 19. `codebase_community.posts.ParentId`

**Profile:** Column ParentId has 44211 NULL values out of 91966 records. There are 29006 distinct values. The minimum value is '1' and the maximum value is '115375'. Most common non-NULL column values (with counts) are '726' (136), '1337' (58), '423' (56), '4551' (42), '5115' (35), '421' (28), '36' (27), '125' (26), '2691' (25), '73' (24). Value lengths range from 1 to 5 characters. Every column value looks like a number. Values are stored as INTEGER.

**Short:** ParentId is an INTEGER column representing the ID of a parent post, containing 44,211 NULLs and distinct values ranging from 1 to 115,375.

**Long:** ParentId stores the ID of a parent post as an INTEGER. It contains 44,211 NULL values out of 91,966 records, with 29,006 distinct non-NULL values ranging from '1' to '115375'. Common values include '726', '1337', and '423'. NULLs indicate posts without a parent (e.g., top-level questions).

**Grade:** **OK**: the NULL interpretation (top-level posts) is a reasonable, hedged inference.

## 20. `card_games.cards.availability`

**Profile:** Column availability has 1 NULL values out of 56822 records. There are 9 distinct values. The minimum value is 'arena' and the maximum value is 'shandalar'. Most common non-NULL column values (with counts) are 'mtgo,paper' (25459), 'paper' (21531), 'arena,mtgo,paper' (4609), 'mtgo' (3697), 'arena' (999), 'arena,paper' (490), 'arena,mtgo' (14), 'shandalar' (12), 'dreamcast' (10). Value lengths range from 4 to 16 characters. Values are stored as TEXT.

**Short:** The availability column stores TEXT values indicating where a card is available, containing comma-separated platform codes like 'mtgo,paper' or single entries such as 'arena'.

**Long:** This TEXT column indicates card availability across platforms. It contains comma-separated literals such as 'mtgo,paper', 'paper', 'arena,mtgo,paper', 'mtgo', 'arena', 'arena,paper', 'arena,mtgo', 'shandalar', and 'dreamcast'. One NULL value exists among 56,822 records. Values range from 4 to 16 characters.

**Grade:** **OK**: lists all 9 literals.
