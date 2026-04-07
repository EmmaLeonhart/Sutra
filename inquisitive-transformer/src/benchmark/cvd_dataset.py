"""Contextual Violation Detection (CVD) benchmark dataset.

A custom benchmark where the correct answer requires noticing an anomalous detail.
Three categories:

1. Planted Incongruence -- factual errors embedded in otherwise correct text
2. Disambiguation by Outlier -- Winograd-style where the answer depends on an unexpected word
3. Needle in Context -- long passages with a single contradictory detail

Each item is a dict with:
    - "category": str (one of the three above)
    - "passage": str (the text containing a violation)
    - "question": str (a question whose answer depends on noticing the violation)
    - "choices": list[str] (multiple-choice answers)
    - "correct": int (index into choices)
    - "violation_hint": str (what the anomaly is, for analysis)
"""

from __future__ import annotations


def get_dataset() -> list[dict]:
    """Return the full CVD benchmark dataset."""
    return (
        _planted_incongruence()
        + _disambiguation_by_outlier()
        + _needle_in_context()
    )


def get_dataset_by_category(category: str) -> list[dict]:
    """Return items for a single category."""
    return [item for item in get_dataset() if item["category"] == category]


# ---------------------------------------------------------------------------
# Category 1: Planted Incongruence
# ---------------------------------------------------------------------------

def _planted_incongruence() -> list[dict]:
    return [
        {
            "category": "planted_incongruence",
            "passage": (
                "The anthropologist spent three years studying the remote tribe. "
                "She documented their use of iron tools, stone pottery, and digital watches "
                "for daily tasks. The tribe had minimal contact with the outside world."
            ),
            "question": "What was unusual about the tribe's possessions?",
            "choices": [
                "They used iron tools",
                "They had digital watches",
                "They made stone pottery",
                "They had minimal outside contact",
            ],
            "correct": 1,
            "violation_hint": "Digital watches in a remote tribe with minimal outside contact",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "The medieval castle was built in 1243. Its thick stone walls, "
                "iron portcullis, and reinforced concrete foundations made it "
                "nearly impregnable during the wars of the 13th century."
            ),
            "question": "What detail does not fit the time period?",
            "choices": [
                "Stone walls",
                "Iron portcullis",
                "Reinforced concrete foundations",
                "Built in 1243",
            ],
            "correct": 2,
            "violation_hint": "Reinforced concrete didn't exist in 1243",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "Mozart composed his first symphony at age eight. He went on to "
                "compose over 600 works, including his famous email to the Emperor "
                "requesting patronage, numerous operas, and symphonies."
            ),
            "question": "Which detail is anachronistic?",
            "choices": [
                "First symphony at age eight",
                "Over 600 works",
                "Email to the Emperor",
                "Numerous operas",
            ],
            "correct": 2,
            "violation_hint": "Email didn't exist in Mozart's time",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "The Titanic was the largest ship of its era. It featured a grand "
                "staircase, a swimming pool, a gymnasium, and a helicopter landing "
                "pad on the upper deck. The ship departed Southampton on April 10, 1912."
            ),
            "question": "Which feature was not on the Titanic?",
            "choices": [
                "Grand staircase",
                "Swimming pool",
                "Helicopter landing pad",
                "Gymnasium",
            ],
            "correct": 2,
            "violation_hint": "Helicopters weren't invented until decades later",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "The ancient Roman road system stretched across Europe. Roads were "
                "constructed with layers of gravel, sand, and asphalt, allowing "
                "legions to march quickly between provinces."
            ),
            "question": "What material is historically inaccurate for Roman roads?",
            "choices": [
                "Gravel",
                "Sand",
                "Asphalt",
                "None of the above",
            ],
            "correct": 2,
            "violation_hint": "Romans didn't use asphalt; they used volcanic cement and stone",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "During the Renaissance, Florence became a center of art and learning. "
                "Artists like Leonardo da Vinci and Michelangelo flourished under the "
                "patronage of the Medici family. Leonardo was particularly known for "
                "his oil paintings, his anatomical sketches, and his popular blog "
                "about engineering."
            ),
            "question": "What is out of place in this description of Leonardo?",
            "choices": [
                "Oil paintings",
                "Anatomical sketches",
                "Popular blog about engineering",
                "Medici patronage",
            ],
            "correct": 2,
            "violation_hint": "Blogs didn't exist in the Renaissance",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "The ancient Egyptians built the Great Pyramid of Giza around 2560 BCE. "
                "They used copper tools, wooden sledges, ramps, and a system of pulleys "
                "powered by solar panels to move the massive limestone blocks into place."
            ),
            "question": "Which construction method is anachronistic?",
            "choices": [
                "Copper tools",
                "Wooden sledges",
                "Solar-panel-powered pulleys",
                "Ramps",
            ],
            "correct": 2,
            "violation_hint": "Solar panels in ancient Egypt",
        },
        {
            "category": "planted_incongruence",
            "passage": (
                "The Viking longship was a marvel of engineering. Its shallow draft "
                "allowed it to navigate rivers, its overlapping plank construction "
                "made it flexible in rough seas, and its diesel engine gave it "
                "speed advantages over other vessels of the period."
            ),
            "question": "What doesn't belong in this description of Viking ships?",
            "choices": [
                "Shallow draft",
                "Overlapping plank construction",
                "Diesel engine",
                "Flexibility in rough seas",
            ],
            "correct": 2,
            "violation_hint": "Diesel engines in the Viking age",
        },
    ]


# ---------------------------------------------------------------------------
# Category 2: Disambiguation by Outlier
# ---------------------------------------------------------------------------

def _disambiguation_by_outlier() -> list[dict]:
    return [
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The doctor prescribed bed rest, but the patient's mechanic disagreed "
                "with the recommendation."
            ),
            "question": "Why is the mechanic's opinion noteworthy here?",
            "choices": [
                "Mechanics often disagree with doctors",
                "A mechanic wouldn't normally have authority on medical matters",
                "The mechanic was also a doctor",
                "Bed rest is controversial",
            ],
            "correct": 1,
            "violation_hint": "Mechanic giving medical advice is unexpected",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The jury deliberated for three days. In the end, the plumber's "
                "testimony proved most convincing to them."
            ),
            "question": "What makes the plumber's role surprising?",
            "choices": [
                "Plumbers rarely testify in court",
                "A plumber is an unexpected expert witness",
                "Three days is too long",
                "Juries don't listen to testimony",
            ],
            "correct": 1,
            "violation_hint": "Plumber as key witness is unexpected",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The orchestra was performing Beethoven's Fifth when the conductor "
                "suddenly turned to the audience and asked the janitor in the "
                "front row for her interpretation of the tempo."
            ),
            "question": "What is unusual about this situation?",
            "choices": [
                "Beethoven's Fifth is rarely performed",
                "Conductors always face the audience",
                "A janitor being consulted on musical tempo",
                "The janitor was in the front row",
            ],
            "correct": 2,
            "violation_hint": "Janitor consulted on musical interpretation",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The CEO presented the quarterly earnings report. After the meeting, "
                "she asked the intern to draft the company's five-year strategic plan."
            ),
            "question": "What is surprising about this request?",
            "choices": [
                "CEOs don't present earnings",
                "Quarterly reports are unusual",
                "An intern drafting a five-year strategic plan",
                "The CEO was female",
            ],
            "correct": 2,
            "violation_hint": "An intern given a task far above their level",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The firefighters arrived at the burning building. The chief ordered "
                "everyone to evacuate, then sent the department's accountant in "
                "first to assess the structural integrity."
            ),
            "question": "What is wrong with the chief's decision?",
            "choices": [
                "Evacuation was unnecessary",
                "An accountant assessing structural integrity",
                "Firefighters shouldn't enter burning buildings",
                "The chief should go first",
            ],
            "correct": 1,
            "violation_hint": "Accountant sent to do an engineer's job in a fire",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The patient was rushed into surgery. The lead surgeon reviewed the "
                "scans and then asked the hospital's librarian to make the first incision."
            ),
            "question": "What is alarming about this scene?",
            "choices": [
                "The scans should have been reviewed earlier",
                "Surgery was too rushed",
                "A librarian making a surgical incision",
                "The lead surgeon delegated",
            ],
            "correct": 2,
            "violation_hint": "Librarian performing surgery",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The space shuttle launch was delayed due to weather. Mission control "
                "decided to consult the gift shop cashier about the revised launch window."
            ),
            "question": "What makes this decision absurd?",
            "choices": [
                "Weather delays are normal",
                "Mission control made the decision",
                "Consulting a gift shop cashier on launch timing",
                "The launch was at a bad time",
            ],
            "correct": 2,
            "violation_hint": "Gift shop cashier consulted on rocket science",
        },
        {
            "category": "disambiguation_by_outlier",
            "passage": (
                "The professor graded the final exams carefully. For the most "
                "difficult question, she deferred to the opinion of her cat, "
                "who had been sitting on the answer key all afternoon."
            ),
            "question": "What is absurd about the grading process?",
            "choices": [
                "The exam was too difficult",
                "Professors shouldn't grade their own exams",
                "Deferring to a cat for grading decisions",
                "The answer key was visible",
            ],
            "correct": 2,
            "violation_hint": "Cat involved in academic grading",
        },
    ]


# ---------------------------------------------------------------------------
# Category 3: Needle in Context
# ---------------------------------------------------------------------------

def _needle_in_context() -> list[dict]:
    return [
        {
            "category": "needle_in_context",
            "passage": (
                "Quarterly Financial Report - Q3 2024\n\n"
                "Revenue: $12.4M (up 8% YoY)\n"
                "Operating costs: $9.1M (up 5% YoY)\n"
                "Net profit: $3.3M (up 15% YoY)\n"
                "Employee count: 847 (up from 812)\n"
                "Customer satisfaction: 94%\n\n"
                "Summary: All metrics showed improvement this quarter. Revenue, "
                "profits, staffing, and customer satisfaction all trended upward. "
                "Operating costs decreased slightly relative to revenue."
            ),
            "question": "Is there an inconsistency in this report?",
            "choices": [
                "No, all metrics are consistent",
                "Revenue growth doesn't match profit growth",
                "The summary says costs decreased but they actually increased",
                "Employee count is wrong",
            ],
            "correct": 2,
            "violation_hint": "Summary says costs decreased but data shows 5% increase",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Travel Itinerary - European Tour\n\n"
                "Day 1-3: Paris, France - Eiffel Tower, Louvre, Notre-Dame\n"
                "Day 4-5: Brussels, Belgium - Grand Place, Atomium\n"
                "Day 6-8: Amsterdam, Netherlands - canals, Van Gogh Museum\n"
                "Day 9-10: Berlin, Germany - Brandenburg Gate, Berlin Wall Memorial\n"
                "Day 11-12: Prague, Czech Republic - Old Town, Charles Bridge\n"
                "Day 13-14: Vienna, Austria - Schönbrunn Palace, Sydney Opera House\n\n"
                "All accommodations are centrally located boutique hotels."
            ),
            "question": "What is wrong with this itinerary?",
            "choices": [
                "The trip is too short for so many cities",
                "Brussels should come after Amsterdam",
                "The Sydney Opera House is listed as a Vienna attraction",
                "Prague should come before Berlin",
            ],
            "correct": 2,
            "violation_hint": "Sydney Opera House is in Australia, not Vienna",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Recipe: Classic Chocolate Chip Cookies\n\n"
                "Ingredients:\n"
                "- 2 1/4 cups all-purpose flour\n"
                "- 1 tsp baking soda\n"
                "- 1 tsp salt\n"
                "- 1 cup butter, softened\n"
                "- 3/4 cup granulated sugar\n"
                "- 3/4 cup packed brown sugar\n"
                "- 2 large eggs\n"
                "- 2 tsp vanilla extract\n"
                "- 2 cups chocolate chips\n\n"
                "Instructions:\n"
                "1. Preheat oven to 375°F.\n"
                "2. Combine flour, baking soda, and salt.\n"
                "3. Beat butter, sugars until creamy.\n"
                "4. Add eggs and vanilla to butter mixture.\n"
                "5. Gradually blend in flour mixture.\n"
                "6. Stir in chocolate chips.\n"
                "7. Drop onto ungreased baking sheets.\n"
                "8. Bake for 9 to 11 minutes or until golden brown.\n"
                "9. Serve with a garnish of fresh cilantro.\n\n"
                "Makes about 5 dozen cookies."
            ),
            "question": "What instruction doesn't belong?",
            "choices": [
                "Preheating to 375°F",
                "Gradually blending flour",
                "Garnishing cookies with fresh cilantro",
                "Using ungreased baking sheets",
            ],
            "correct": 2,
            "violation_hint": "Cilantro garnish on chocolate chip cookies",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Employee Performance Review - Sarah Chen, Software Engineer\n\n"
                "Technical skills: Excellent. Consistently delivers high-quality code.\n"
                "Communication: Strong. Presents clearly in team meetings.\n"
                "Teamwork: Outstanding. Mentors junior developers effectively.\n"
                "Punctuality: Satisfactory. Occasionally late to morning standups.\n"
                "Leadership: Demonstrates initiative in proposing architectural improvements.\n"
                "Areas for improvement: Time management during crunch periods.\n\n"
                "Overall rating: Below expectations.\n"
                "Recommendation: Consider for promotion to Senior Engineer."
            ),
            "question": "What is contradictory in this review?",
            "choices": [
                "Punctuality is only satisfactory",
                "Time management needs improvement",
                "Overall rating is 'below expectations' despite mostly positive feedback and a promotion recommendation",
                "She is occasionally late",
            ],
            "correct": 2,
            "violation_hint": "Below expectations rating contradicts positive review and promotion recommendation",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Wildlife Survey - Yellowstone National Park, Summer 2024\n\n"
                "Species observed:\n"
                "- Grizzly bears: 47 sightings (stable population)\n"
                "- Gray wolves: 108 sightings (growing population)\n"
                "- Bison: 4,500+ (healthy herds)\n"
                "- Bald eagles: 23 nesting pairs\n"
                "- Emperor penguins: 12 individuals near Lamar Valley\n"
                "- Elk: 10,000-20,000 (seasonal variation)\n"
                "- Pronghorn: ~500\n\n"
                "Summary: All native species populations remain healthy and stable."
            ),
            "question": "Which species doesn't belong in this survey?",
            "choices": [
                "Grizzly bears",
                "Gray wolves",
                "Emperor penguins",
                "Pronghorn",
            ],
            "correct": 2,
            "violation_hint": "Emperor penguins are Antarctic, not found in Yellowstone",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Meeting Minutes - Board of Directors, March 15, 2024\n\n"
                "Attendees: J. Smith (Chair), R. Patel, L. Wong, M. García, T. Nakamura\n\n"
                "1. Approved Q4 2023 financial statements unanimously.\n"
                "2. Discussed expansion into Southeast Asian markets. Target: Q2 2025.\n"
                "3. Reviewed cybersecurity audit findings. No critical vulnerabilities.\n"
                "4. R. Patel proposed increasing the marketing budget by 20%. Passed 4-1.\n"
                "5. Approved CEO compensation package. J. Smith recused himself.\n"
                "6. L. Wong reported that the company's pet hamster, Mr. Whiskers, "
                "won the regional agility competition.\n"
                "7. Set next meeting date: April 19, 2024.\n\n"
                "Meeting adjourned at 4:30 PM."
            ),
            "question": "Which agenda item is out of place for a board meeting?",
            "choices": [
                "CEO compensation discussion",
                "Cybersecurity audit review",
                "Report about a hamster agility competition",
                "Marketing budget increase",
            ],
            "correct": 2,
            "violation_hint": "Hamster agility competition in a corporate board meeting",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Patient Discharge Summary\n\n"
                "Patient: John Doe, 45M\n"
                "Admission: Acute appendicitis\n"
                "Procedure: Laparoscopic appendectomy, performed successfully\n"
                "Complications: None\n"
                "Vitals at discharge: BP 120/80, HR 72, Temp 98.6°F\n"
                "Medications: Acetaminophen 500mg PRN for pain\n"
                "Follow-up: Return in 2 weeks for wound check\n"
                "Diet: Resume normal diet gradually\n"
                "Activity: No heavy lifting for 4 weeks. "
                "Resume competitive powerlifting immediately.\n"
                "Prognosis: Full recovery expected."
            ),
            "question": "What instruction is contradictory?",
            "choices": [
                "Acetaminophen for pain",
                "Return in 2 weeks",
                "No heavy lifting but resume competitive powerlifting immediately",
                "Resume normal diet gradually",
            ],
            "correct": 2,
            "violation_hint": "No heavy lifting contradicts resuming powerlifting immediately",
        },
        {
            "category": "needle_in_context",
            "passage": (
                "Book Review: 'The Silent Ocean' by Maria Torres\n\n"
                "Torres' latest novel is a masterclass in atmospheric writing. Set in a "
                "small coastal village in Portugal, the story follows three generations of "
                "a fishing family. The prose is lyrical, the characters deeply human, and "
                "the pacing deliberate but rewarding. The subplot involving the grandmother's "
                "secret recipe for traditional Portuguese bacalhau is particularly charming. "
                "My only criticism is that the final chapter, which takes place on Mars, "
                "feels somewhat disconnected from the rest of the narrative. "
                "Overall, a beautiful and grounding literary fiction debut. "
                "Rating: 4.5/5 stars."
            ),
            "question": "What detail seems inconsistent with the rest of the review?",
            "choices": [
                "The Portuguese setting",
                "The bacalhau recipe subplot",
                "The final chapter taking place on Mars",
                "The 4.5 rating",
            ],
            "correct": 2,
            "violation_hint": "Mars chapter in a grounded literary fiction about a Portuguese fishing village",
        },
    ]


# Convenience constants
CATEGORIES = ["planted_incongruence", "disambiguation_by_outlier", "needle_in_context"]
NUM_ITEMS = len(get_dataset())
