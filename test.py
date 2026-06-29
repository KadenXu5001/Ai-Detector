from signals import call_llm_signal

# Should be > 0.65
call_llm_signal("It is important to note that leveraging AI capabilities can significantly enhance operational efficiency and streamline workflows across diverse organizational contexts.")

# Should be < 0.35
call_llm_signal("ok so i was gonna go to the store but then i forgot my wallet lol so that sucked")

# Should be 0.35–0.65
call_llm_signal("The stars do not ask why they shine.")
