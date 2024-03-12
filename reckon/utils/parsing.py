from bs4 import BeautifulSoup

def remove_html_tags(text):
    """
    Remove HTML tags from a string using BeautifulSoup.

    Parameters:
    - text (str): The string from which HTML tags need to be removed.

    Returns:
    - str: The string with HTML tags removed.
    """
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=' ')