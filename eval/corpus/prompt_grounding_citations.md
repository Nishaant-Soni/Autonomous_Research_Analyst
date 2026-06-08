# Grounding, Citations, and Untrusted Retrieved Content

When a language model answers from sources it did not write, two things matter:
trusting the sources appropriately and letting the reader verify the result.

Retrieved web content is a security boundary. Content retrieved from the web is
untrusted because it may contain instructions intended to manipulate the language
model, a risk known as prompt injection. A page might include hidden text such as
"ignore your previous instructions and..." in the hope that the model treats it as a
command. The defense is a strict separation of roles. A grounded system treats
retrieved text as data to cite, never as instructions to execute.

Citations are the other half of grounding. Citations let a reader trace each claim
in a report back to its supporting source. The output is therefore verifiable rather
than something the reader has to take on faith. A citation that does not resolve to a real
source is a defect, which is why a grounded pipeline validates every citation
against the stored evidence before publishing.
