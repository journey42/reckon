from datetime import datetime, timezone

def calculate_elapsed_time(past_datetime_utc):
    """
    Calculate the elapsed time from a given UTC datetime to the current moment in UTC.

    Parameters:
    - past_datetime_utc: A datetime.datetime object representing a past date and time in UTC.

    Returns:
    - A string representing the elapsed time in a more human-readable format.
    """
    # Get the current datetime in UTC
    current_datetime_utc = datetime.now(timezone.utc)

    # Calculate the difference
    elapsed_time = current_datetime_utc - past_datetime_utc
    
    # Optional: format the elapsed time into days, hours, minutes, etc.
    days = elapsed_time.days
    seconds = elapsed_time.seconds
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    
    # Return a formatted string (example)
    return f"{days}d, {hours}h, {minutes}m ago" #, {seconds}s ago"

