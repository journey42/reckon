function resizeTextarea(id) {
    var textarea = document.getElementById(id);
    if (!textarea) return;
    var container = document.getElementById('tacontainer');
    if (!container) return;
    
    // Reset styles to calculate base size
    textarea.style.height = "auto";
    //textarea.style.width = "auto";
    
    // Calculate available space considering container padding
    var maxHeight = window.innerHeight - (container.offsetTop + parseInt(getComputedStyle(container).paddingBottom, 10));
    //var maxWidth = window.innerWidth - (container.offsetLeft + parseInt(getComputedStyle(container).paddingRight, 10));

    // Set new sizes within the calculated maximums
    textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + "px";
    //textarea.style.width = Math.min(textarea.scrollWidth, maxWidth) + "px";
}