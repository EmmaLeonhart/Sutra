"""Benchmark scenarios for evaluating Neurosymbolic GraphRAG vs Standard RAG.

Each scenario targets a specific failure mode of cosine-similarity retrieval:
distractors that rank higher than causally-essential chain steps.

7 scenarios across diverse domains, each with a multi-hop reasoning chain
and carefully designed distractors.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    id: str                          # e.g. "drug_interaction"
    name: str                        # Human-readable title
    description: str                 # Why standard RAG struggles here
    failure_mode: str                # Category label for the failure type
    query: str
    corpus: list[str]
    ground_truth_indices: list[int]  # Indices into corpus forming the chain
    expected_answer_keywords: list[str]
    chain_length: int                # Number of hops in the reasoning chain

    @property
    def ground_truth_chain(self) -> list[str]:
        """The ordered list of corpus sentences forming the correct chain."""
        return [self.corpus[i] for i in self.ground_truth_indices]

    def ground_truth_coverage(self, retrieved: list[str]) -> float:
        """Fraction of ground-truth sentences present in *retrieved*."""
        chain = self.ground_truth_chain
        hits = sum(1 for gt in chain if gt in retrieved)
        return hits / len(chain)


# ── Scenario 0: Everest Boiling Point ──────────────────────────────────────────
# Copied from knowledge_base.py — the original demo scenario

_everest_corpus = [
    # Ground-truth chain (4 sentences)
    "Water boils at 100 degrees Celsius at standard atmospheric pressure.",          # 0
    "Atmospheric pressure decreases as altitude increases.",                          # 1
    "The summit of Mount Everest is approximately 8,849 meters above sea level.",     # 2
    "At high altitudes where atmospheric pressure is lower, "
    "water boils at a lower temperature, roughly 70 degrees Celsius on Everest.",     # 3
    # Distractors
    "Mount Everest is located on the border between Nepal and Tibet.",                # 4
    "Water is composed of two hydrogen atoms and one oxygen atom.",                   # 5
    "The Dead Sea is the lowest point on Earth's surface.",                           # 6
    "Boiling is a phase transition from liquid to gas.",                              # 7
    "Edmund Hillary and Tenzing Norgay were the first to summit Everest in 1953.",    # 8
    "Pure water freezes at 0 degrees Celsius at standard pressure.",                  # 9
    "The atmospheric pressure at sea level is approximately 101.325 kPa.",            # 10
    "Mount Kilimanjaro is the highest peak in Africa.",                               # 11
]


# ── Scenario 1: Drug Interaction ───────────────────────────────────────────────
# 5-hop chain: patient→drug→enzyme→metabolism→bleeding risk
# Failure: cross-domain entity bridging (clinical→molecular)

_drug_corpus = [
    # Ground-truth chain (5 sentences)
    "Warfarin is an anticoagulant drug that inhibits vitamin K-dependent "
    "clotting factors to prevent blood clot formation.",                              # 0
    "Warfarin is primarily metabolized by the cytochrome P450 enzyme CYP2C9 "
    "in the liver.",                                                                 # 1
    "Ketoconazole is a potent inhibitor of multiple cytochrome P450 enzymes "
    "including CYP3A4 and CYP2C9.",                                                  # 2
    "When CYP2C9 is inhibited, warfarin metabolism slows dramatically, "
    "causing plasma warfarin levels to rise.",                                        # 3
    "Elevated warfarin levels lead to excessive anticoagulation and a high risk "
    "of spontaneous bleeding events.",                                               # 4
    # Distractors (topically similar, causally irrelevant)
    "Warfarin was originally developed as a rat poison in the 1940s.",                # 5
    "The liver is the largest internal organ in the human body.",                     # 6
    "Ketoconazole is commonly used to treat fungal infections of the skin.",          # 7
    "Vitamin K is found abundantly in leafy green vegetables like spinach.",          # 8
    "Blood clotting involves a complex cascade of over 12 coagulation factors.",      # 9
    "CYP3A4 is the most abundant cytochrome P450 enzyme in the human liver.",         # 10
    "Aspirin is another anticoagulant that works by inhibiting platelet "
    "aggregation.",                                                                  # 11
    "The international normalized ratio (INR) is used to monitor "
    "anticoagulant therapy.",                                                        # 12
    "Drug interactions are a leading cause of adverse events in "
    "hospitalized patients.",                                                        # 13
]


# ── Scenario 2: Economic Cascade ──────────────────────────────────────────────
# 4-hop chain: drought→crop→supply→price
# Failure: trap distractors match query terms but give wrong cause

_economic_corpus = [
    # Ground-truth chain (4 sentences)
    "A severe drought in Brazil's Minas Gerais region destroyed 40 percent of "
    "the arabica coffee harvest in the 2024 growing season.",                        # 0
    "Brazil supplies approximately 35 percent of the world's arabica coffee "
    "beans, making it the dominant single-country source.",                           # 1
    "When a dominant supplier loses a significant portion of its harvest, "
    "global commodity supply contracts and spot prices increase sharply.",             # 2
    "Retail coffee prices in the United States rose 22 percent in early 2025, "
    "driven primarily by the supply shortage from Brazil.",                           # 3
    # Distractors
    "Vietnam is the world's largest producer of robusta coffee beans.",               # 4
    "Coffee futures are traded on the Intercontinental Exchange (ICE).",              # 5
    "The US Federal Reserve raised interest rates in 2024, increasing costs "
    "for importers.",                                                                # 6
    "Shipping container rates from South America to the US doubled in 2023 "
    "due to port congestion.",                                                       # 7
    "Climate change is expected to reduce global coffee-growing area by "
    "50 percent by 2050.",                                                           # 8
    "Starbucks announced a 5 percent price increase on all beverages "
    "in January 2025.",                                                              # 9
    "Colombia experienced record coffee production in 2024, offsetting "
    "some regional shortfalls.",                                                     # 10
    "Consumer demand for specialty coffee has grown 15 percent annually "
    "since 2020.",                                                                   # 11
]


# ── Scenario 3: Coral Reef Collapse ───────────────────────────────────────────
# 4-hop chain: CO2→ocean pH→carbonate→coral
# Failure: key step crosses atmospheric→oceanic domain boundary

_coral_corpus = [
    # Ground-truth chain (4 sentences)
    "Anthropogenic carbon dioxide emissions have increased atmospheric CO2 "
    "concentration from 280 ppm pre-industrial to over 420 ppm in 2024.",            # 0
    "Approximately 30 percent of atmospheric CO2 is absorbed by the ocean, "
    "where it reacts with water to form carbonic acid, lowering seawater pH.",        # 1
    "Lower seawater pH reduces the concentration of dissolved carbonate ions "
    "that marine organisms need to build calcium carbonate structures.",              # 2
    "Coral reefs require adequate carbonate ion concentrations to maintain "
    "their calcium carbonate skeletons; ocean acidification causes net "
    "dissolution and reef collapse.",                                                # 3
    # Distractors
    "Coral reefs support approximately 25 percent of all marine species.",            # 4
    "The Great Barrier Reef spans over 2,300 kilometers along Australia's "
    "northeast coast.",                                                              # 5
    "Rising ocean temperatures cause coral bleaching by expelling symbiotic "
    "zooxanthellae algae.",                                                          # 6
    "Overfishing disrupts reef ecosystems by removing key herbivorous fish "
    "species.",                                                                      # 7
    "Plastic pollution accumulates on coral reefs and blocks sunlight needed "
    "for photosynthesis.",                                                           # 8
    "Marine protected areas have been shown to improve reef health in "
    "some regions.",                                                                 # 9
    "The pH of seawater has decreased by 0.1 units since the industrial "
    "revolution, representing a 26 percent increase in acidity.",                    # 10
    "Carbon capture and storage technology aims to reduce atmospheric "
    "CO2 levels.",                                                                   # 11
    "Limestone, a sedimentary rock, is composed primarily of calcium "
    "carbonate from ancient marine organisms.",                                      # 12
]


# ── Scenario 4: Bridge Collapse ───────────────────────────────────────────────
# 4-hop chain: chloride→corrosion→tendon→failure
# Failure: misleading distractor ("snow and ice load") has max similarity to query

_bridge_corpus = [
    # Ground-truth chain (4 sentences)
    "De-icing salts applied to road surfaces during winter contain sodium "
    "chloride that dissolves in meltwater and penetrates concrete pores.",            # 0
    "Chloride ions that reach embedded steel reinforcement break down the "
    "passive oxide layer, initiating electrochemical corrosion.",                     # 1
    "Corrosion of pre-stressed steel tendons reduces their cross-sectional "
    "area and load-bearing capacity below design thresholds.",                        # 2
    "When tendon capacity drops below the factored load demand, the bridge "
    "girder fails in a sudden brittle fracture mode.",                               # 3
    # Distractors
    "Snow and ice loads on bridge decks can exceed 5 kPa in northern climates "
    "and are a primary design consideration.",                                       # 4
    "The Morandi Bridge in Genoa collapsed in 2018 due to stay-cable "
    "corrosion issues.",                                                             # 5
    "Concrete has high compressive strength but very low tensile strength.",          # 6
    "Bridge inspections in the United States are required every two years "
    "under federal regulations.",                                                    # 7
    "Fatigue cracking in steel bridges is caused by repeated cyclic loading "
    "from traffic.",                                                                 # 8
    "Seismic retrofitting of bridges involves adding base isolation bearings "
    "and column jacketing.",                                                         # 9
    "The Golden Gate Bridge uses a suspension design with cables under "
    "constant tension.",                                                             # 10
    "Fiber-reinforced polymer (FRP) bars are a corrosion-resistant alternative "
    "to steel reinforcement.",                                                       # 11
    "Temperature gradients across a bridge deck cause differential thermal "
    "expansion and internal stresses.",                                              # 12
]


# ── Scenario 5: Antibiotic Resistance ─────────────────────────────────────────
# 5-hop chain: plasmid→gene→enzyme→hydrolysis→resistance
# Failure: molecular entities (beta-lactamase, beta-lactam ring) invisible in query

_antibiotic_corpus = [
    # Ground-truth chain (5 sentences)
    "Bacteria can acquire antibiotic resistance genes through horizontal "
    "gene transfer via conjugative plasmids.",                                       # 0
    "The blaTEM-1 gene carried on many plasmids encodes the enzyme "
    "TEM-1 beta-lactamase.",                                                        # 1
    "TEM-1 beta-lactamase catalyzes the hydrolysis of the beta-lactam ring, "
    "the core structural component shared by penicillin-class antibiotics.",          # 2
    "Hydrolysis of the beta-lactam ring inactivates the antibiotic before "
    "it can bind to penicillin-binding proteins on the bacterial cell wall.",         # 3
    "Without functional antibiotic binding, the bacterium continues cell wall "
    "synthesis normally, rendering the antibiotic treatment ineffective.",            # 4
    # Distractors
    "Alexander Fleming discovered penicillin in 1928 from the mold "
    "Penicillium notatum.",                                                          # 5
    "MRSA (methicillin-resistant Staphylococcus aureus) is a major concern "
    "in hospital-acquired infections.",                                              # 6
    "Antibiotic stewardship programs aim to reduce unnecessary prescriptions "
    "and slow resistance development.",                                              # 7
    "Bacteria reproduce through binary fission, doubling their population "
    "approximately every 20 minutes under ideal conditions.",                        # 8
    "The World Health Organization lists antibiotic resistance as one of "
    "the top 10 global public health threats.",                                      # 9
    "Phage therapy uses bacteriophages to target and kill specific bacterial "
    "strains as an alternative to antibiotics.",                                     # 10
    "Broad-spectrum antibiotics like tetracyclines inhibit bacterial protein "
    "synthesis by binding to the 30S ribosomal subunit.",                            # 11
    "Biofilm formation on medical devices provides bacteria with protection "
    "against both antibiotics and immune responses.",                                # 12
    "Carbapenem-resistant Enterobacteriaceae (CRE) are considered an urgent "
    "threat by the CDC.",                                                            # 13
]


# ── Scenario 6: Satellite Signal Degradation ──────────────────────────────────
# 4-hop chain: solar→magnetic→ionospheric→GPS
# Failure: 4-domain chain (solar physics→magnetosphere→atmosphere→engineering)

_satellite_corpus = [
    # Ground-truth chain (4 sentences)
    "Coronal mass ejections (CMEs) from the sun release billions of tons of "
    "magnetized plasma that travel through interplanetary space at speeds "
    "up to 3,000 km/s.",                                                            # 0
    "When a CME impacts Earth's magnetosphere, it compresses the magnetic "
    "field and drives geomagnetic storms that inject energetic particles "
    "into the upper atmosphere.",                                                    # 1
    "Energetic particle injection dramatically increases electron density "
    "in the ionosphere, causing rapid fluctuations in the ionospheric "
    "total electron content (TEC).",                                                 # 2
    "GPS signals passing through a disturbed ionosphere experience variable "
    "group delay and phase advance, introducing positioning errors that "
    "can exceed 10 meters.",                                                         # 3
    # Distractors
    "The GPS constellation consists of 31 operational satellites orbiting "
    "at approximately 20,200 km altitude.",                                          # 4
    "Solar panels on spacecraft degrade over time due to radiation exposure "
    "in the Van Allen belts.",                                                       # 5
    "Tropospheric water vapor causes a frequency-independent delay in all "
    "radio signals, including GPS.",                                                 # 6
    "The Carrington Event of 1859 was the most powerful geomagnetic storm "
    "ever recorded, causing telegraph system failures worldwide.",                   # 7
    "Multipath errors occur when GPS signals reflect off buildings and "
    "terrain before reaching the receiver.",                                         # 8
    "Differential GPS (DGPS) uses ground reference stations to correct "
    "satellite positioning errors in real time.",                                    # 9
    "The ionosphere extends from approximately 60 km to 1,000 km above "
    "Earth's surface and is ionized by solar ultraviolet radiation.",                 # 10
    "Galileo is the European Union's global navigation satellite system, "
    "designed to be interoperable with GPS.",                                        # 11
    "Space weather forecasting relies on solar observatories like SOHO "
    "and the Solar Dynamics Observatory.",                                           # 12
]


# ── All Scenarios ─────────────────────────────────────────────────────────────

SCENARIOS: list[Scenario] = [
    Scenario(
        id="everest_boiling",
        name="Everest Boiling Point",
        description="4-hop chain linking altitude→pressure→boiling point. "
                    "Distractors about Everest geography and water chemistry "
                    "rank higher by similarity but are causally irrelevant.",
        failure_mode="Low-similarity intermediates",
        query="At what temperature does water boil on Mount Everest?",
        corpus=_everest_corpus,
        ground_truth_indices=[0, 1, 2, 3],
        expected_answer_keywords=["70", "lower", "boil"],
        chain_length=4,
    ),
    Scenario(
        id="drug_interaction",
        name="Drug Interaction Chain",
        description="5-hop chain: warfarin→CYP2C9→ketoconazole inhibition→"
                    "elevated levels→bleeding. Standard RAG fails because "
                    "the molecular enzyme bridge (CYP2C9) has low similarity "
                    "to the clinical query about bleeding risk.",
        failure_mode="Cross-domain entity bridging",
        query="Why might a patient on warfarin experience dangerous bleeding "
              "after starting ketoconazole?",
        corpus=_drug_corpus,
        ground_truth_indices=[0, 1, 2, 3, 4],
        expected_answer_keywords=["CYP2C9", "inhibit", "bleeding"],
        chain_length=5,
    ),
    Scenario(
        id="economic_cascade",
        name="Economic Supply Cascade",
        description="4-hop chain: drought→harvest loss→supply contraction→"
                    "price rise. Distractors about interest rates, shipping "
                    "costs, and Starbucks pricing match 'coffee price' queries "
                    "but give the wrong causal explanation.",
        failure_mode="Trap distractors",
        query="Why did retail coffee prices in the US rise sharply in early 2025?",
        corpus=_economic_corpus,
        ground_truth_indices=[0, 1, 2, 3],
        expected_answer_keywords=["drought", "Brazil", "supply"],
        chain_length=4,
    ),
    Scenario(
        id="coral_reef_collapse",
        name="Coral Reef Collapse",
        description="4-hop chain: CO2→ocean acidification→carbonate loss→"
                    "reef dissolution. The critical atmospheric→oceanic domain "
                    "crossing (CO2 absorption) has low similarity to 'coral reef' "
                    "queries.",
        failure_mode="Cross-domain boundary",
        query="How do carbon dioxide emissions cause coral reef collapse?",
        corpus=_coral_corpus,
        ground_truth_indices=[0, 1, 2, 3],
        expected_answer_keywords=["carbonate", "acidification", "pH"],
        chain_length=4,
    ),
    Scenario(
        id="bridge_collapse",
        name="Bridge Collapse Mechanism",
        description="4-hop chain: chloride→corrosion→tendon loss→fracture. "
                    "The distractor about snow/ice loads has maximum similarity "
                    "to 'bridge collapse' but is the wrong failure mode.",
        failure_mode="Misleading high-similarity distractor",
        query="How can de-icing salts cause a bridge to collapse?",
        corpus=_bridge_corpus,
        ground_truth_indices=[0, 1, 2, 3],
        expected_answer_keywords=["chloride", "corrosion", "tendon"],
        chain_length=4,
    ),
    Scenario(
        id="antibiotic_resistance",
        name="Antibiotic Resistance Mechanism",
        description="5-hop chain: plasmid→gene→enzyme→ring hydrolysis→"
                    "treatment failure. Molecular entities like beta-lactamase "
                    "and beta-lactam ring are invisible in a clinical query "
                    "about 'why antibiotics stop working'.",
        failure_mode="Molecular entities invisible in query",
        query="How do bacteria become resistant to penicillin-class antibiotics?",
        corpus=_antibiotic_corpus,
        ground_truth_indices=[0, 1, 2, 3, 4],
        expected_answer_keywords=["beta-lactamase", "plasmid", "hydrolysis"],
        chain_length=5,
    ),
    Scenario(
        id="satellite_signal",
        name="Satellite Signal Degradation",
        description="4-hop chain crossing 4 domains: solar CME→geomagnetic "
                    "storm→ionospheric disturbance→GPS error. Each hop changes "
                    "the scientific domain, so no single query can be similar "
                    "to all chain steps.",
        failure_mode="Multi-domain chain",
        query="How do solar storms cause GPS positioning errors?",
        corpus=_satellite_corpus,
        ground_truth_indices=[0, 1, 2, 3],
        expected_answer_keywords=["ionosphere", "electron", "delay"],
        chain_length=4,
    ),
]


def get_scenario(scenario_id: str) -> Scenario:
    """Look up a scenario by ID. Raises KeyError if not found."""
    for s in SCENARIOS:
        if s.id == scenario_id:
            return s
    raise KeyError(f"Unknown scenario: {scenario_id!r}. "
                   f"Available: {[s.id for s in SCENARIOS]}")
