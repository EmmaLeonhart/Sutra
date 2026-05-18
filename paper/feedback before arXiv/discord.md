 [EAI], 
maniospas — 5/9/2026 11:42 AM
PLs are not my main domain (I'm mainly a ML person), but I'm reasonably confident on these suggestions - would make them if I was reviewing it, though perhaps after thinking more (take them with a grain of salt):
fuzzy neural nets exist as a concept. you probably need to reference and cite them in the background
contributions should be a small list of bullet points. their main text should reside under the main methodology
don't merge methodology and experiment details in section 3. have a dedicated experiment section.
conversely, section 4 is too small to be a standalone section. it could be merged with the novelties and methodology in section 3 and have experiments in section 4
the manuscript is missing language snippets. likewise, examples of precomputed rotation matrices are needed for a small toy setting
don't describe accuracy's progress but plot it over time. it is also not clear if fuzzy accuracy is presented as accuracy (which would ideally actually be formulated as a loss or -given the fuzzy framing- as a gain function). what is the impact of hyperparameters? consider adding more experiment results to demonstrate applicability and reference appendix insights
experiments in general do not differentiate between training and test accuracy to demonstrate generalization of architectures. this is not the main point of the paper, but still required as proper scientific methodology. aggregate of experiment runs are also needed.
since converegence is studied, please mention std after the knee point identified
mention that adam has its introductory paper's default other paramaters and cite it - in general some more and more recent citations would beneeded

otherwise a normal paper. hope it helps.

P.S. got into strict reviewer mode while reading, which is a good indication probably. i only hope I'm not sounding too mean for a casual conversation
oh, also, choose a venue carefully. this would definitely not get accepted in a ML conference's research track because it's too technical/the theoretical progress is kind of burried inside the details. but I think that other tracks or PL conferences like this format. cannot tell for sure though
honestly I was gonna recommend submitting it to softwarex, but then remembered that those journals have enormous processing charges which we kind of usually have our unis or orgs pay for in academia.
Kamidere [EAI],  — 5/9/2026 11:55 AM
I submitted it to NeurIPS earlier. Suggestions on the venue? Ones that allow for less strict page limits would probably be better.
akhilRole icon, Moderator — 5/9/2026 12:16 PM
lmfao
 [EAI], 
maniospas — 5/9/2026 12:28 PM
don't really have good suggestions because we never format our work this way (I'd like to though). 
realistically, you can submit even in those kinds of conferences. but you do need to focus a lot more on the scientific part and less on technical.

to keep the current spirit, probably some of the more technical tracks of PKDD could work, but it's well beyond submission time. also be aware that popular stuff like neurips has a huge rejection ratio, especially with AI slop papers flooding in and muddling the waters
oh, also if you're an individual (and not submitting as part of an org to fund you): you do need to register to conferences and present live if you are accepted, so dunno if you have accounted for that budget.
to give you an idea, before the latest wave of inflation i used to incur at least 1500$ for travels, hotels, registration, and expenses for my institute for each conference paper they wanted me to submit and present, and this given that we targetted same-continent events.
Kamidere [EAI],  — 5/9/2026 12:34 PM
I have accounted for that in my budget. It's going to be difficult but I think that it will be a significant financial return anyways, and at least with NeurIPS I believe I can get some funding
I think that the most important thing career-wise for me is more being able to actually get onto arXiv (CS.AI) rather than conference acceptance. At the very least arXiv endorsement is a bigger bottleneck on my progress than conference acceptance.
maniospas — 5/9/2026 12:42 PM
ah, dangit. i'm registered in arxiv with my work email and not allowed to endorse people 
maybe try zenodo which is more open
also, maybe we can goto ⁠careers for more?
{} /s /j [PLTD],  — 5/9/2026 12:58 PM
thats dumb 
u gotta pay more to endorse or smth?
maniospas — 5/9/2026 1:02 PM
no, it's because there is a clear linked affiliation. 
i'll actually ask on monday though, because it's kind of a default but never got it in writing and could be wrong.