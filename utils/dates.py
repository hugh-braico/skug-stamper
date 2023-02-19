from datetime import date, timedelta
from sys import exit

def infer_last_weekday(weekday: str) -> str:
	weekday_mapping = {
		"Monday":    0,
		"Tuesday":   1, 
		"Wednesday": 2, 
		"Thursday":  3, 
		"Friday":    4, 
		"Saturday":  5, 
		"Sunday":    6
	}
	if weekday not in weekday_mapping:
		exit(f"ERROR: Invalid DAY value {weekday}!")

	weekday_number = weekday_mapping[weekday]

	day_counter = date.today()

	# Get the last weekday that matches the weekday 
	# Doesn't need to be efficient
	while day_counter.weekday() != weekday_number:
		day_counter = day_counter - timedelta(days=1)

	return day_counter.isoformat()


def get_weekday_name(weekday: int) -> str:
	weekday_mapping = {
		0: "Monday",
		1: "Tuesday", 
		2: "Wednesday", 
		3: "Thursday", 
		4: "Friday", 
		5: "Saturday", 
		6: "Sunday"
	}
	return weekday_mapping[weekday]