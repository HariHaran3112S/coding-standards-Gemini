function showLoader() {
    document.getElementById("loader").style.display = "flex";
}

function copyRevisedCode() {
    const codeBlock = document.getElementById("revisedCode");
    const text = codeBlock.innerText;

    navigator.clipboard.writeText(text).then(() => {
        alert("✅ Revised code copied to clipboard!");
    }).catch(err => {
        alert("❌ Failed to copy code: " + err);
    });
}
