const fileInput = document.getElementById("file-input");
const solveBtn  = document.getElementById("solve-btn");
const statusMsg = document.getElementById("status-msg");
const resultImg = document.getElementById("result-img");

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0]; 
  if (!file) return;   //user opened the picker and cancelled

  const reader = new FileReader();
  reader.onload = () => {      
    resultImg.src = reader.result;
    resultImg.hidden = false;
  };
  reader.readAsDataURL(file);

  statusMsg.textContent = "";
  solveBtn.disabled = false;
});

solveBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  solveBtn.disabled = true;
  statusMsg.textContent = "Solving…";

  const form = new FormData();
  form.append("file", file);

  try {
    const response = await fetch("/solve", { method: "POST", body: form });

    if (!response.ok) {
      let detail = `Server error (${response.status})`;
      try { detail = (await response.json()).detail ?? detail; } catch {}
      showFailure(detail);
      return;
    }

    const data = await response.json(); 

    if (data.status === "OK") {
      resultImg.src = "data:image/png;base64," + data.image;
      resultImg.hidden = false;
      statusMsg.textContent = data.message;
    } else {
      showFailure(data.message); 
    }
  } catch (err) {
    showFailure("Could not reach the server.");
  } finally {
    solveBtn.disabled = false;
  }
});

function showFailure(message) {
  statusMsg.textContent = message;
  resultImg.hidden = true;
  resultImg.src = "";
}