const API_URL = "http://127.0.0.1:8000";

let token = localStorage.getItem("token");
let userId = localStorage.getItem("userId");
let userName = localStorage.getItem("userName");


// =========================
// PAGE LOAD
// =========================

window.onload = function () {
    if (token && userId) {
        showDashboard();
        loadWallet();
    }
};


// =========================
// LOGIN
// =========================

async function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const message = document.getElementById("login-message");

    if (!email || !password) {
        message.textContent = "Please enter email and password.";
        return;
    }

    const formData = new URLSearchParams();

    formData.append("username", email);
    formData.append("password", password);

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail || "Login failed.";
            return;
        }

        token = data.access_token;
        userId = data.user_id;
        userName = data.name;

        localStorage.setItem("token", token);
        localStorage.setItem("userId", userId);
        localStorage.setItem("userName", userName);

        message.textContent = "";

        showDashboard();
        loadWallet();

    } catch (error) {
        message.textContent = "Cannot connect to MiniPay backend.";
        console.error(error);
    }
}


// =========================
// SHOW DASHBOARD
// =========================

function showDashboard() {
    document.getElementById("login-section").classList.add("hidden");
    document.getElementById("dashboard-section").classList.remove("hidden");

    document.getElementById("user-name").textContent = userName;
}


// =========================
// LOAD WALLET
// =========================

async function loadWallet() {
    try {
        const response = await fetch(
            `${API_URL}/wallet/${userId}`,
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Unable to load wallet.");
            return;
        }

        const rupees = data.balance_paise / 100;

        document.getElementById("balance").textContent =
            rupees.toFixed(2);

    } catch (error) {
        console.error(error);
        alert("Cannot connect to MiniPay backend.");
    }
}


// =========================
// ADD MONEY
// =========================

async function addMoney() {
    const amount = parseFloat(
        document.getElementById("add-money").value
    );

    const message = document.getElementById("money-message");

    if (!amount || amount <= 0) {
        message.textContent = "Enter a valid amount.";
        return;
    }

    const paise = Math.round(amount * 100);

    try {
        const response = await fetch(
            `${API_URL}/wallet/${userId}/add-money?amount_paise=${paise}`,
            {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail || "Failed to add money.";
            return;
        }

        message.textContent = "Money added successfully.";

        document.getElementById("add-money").value = "";

        loadWallet();

    } catch (error) {
        console.error(error);
        message.textContent = "Cannot connect to backend.";
    }
}


// =========================
// TRANSFER MONEY
// =========================

async function transferMoney() {
    const receiverId = parseInt(
        document.getElementById("receiver-id").value
    );

    const amount = parseFloat(
        document.getElementById("transfer-amount").value
    );

    const message = document.getElementById("transfer-message");

    if (!receiverId || !amount || amount <= 0) {
        message.textContent = "Enter valid receiver ID and amount.";
        return;
    }

    const paise = Math.round(amount * 100);

    try {
        const response = await fetch(
            `${API_URL}/transfer`,
            {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    receiver_id: receiverId,
                    amount_paise: paise
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent =
                data.detail || "Transfer failed.";
            return;
        }

        message.textContent =
            `Transfer successful. Transaction ID: ${data.transaction_id}`;

        document.getElementById("receiver-id").value = "";
        document.getElementById("transfer-amount").value = "";

        loadWallet();
        loadTransactions();

    } catch (error) {
        console.error(error);
        message.textContent = "Cannot connect to backend.";
    }
}


// =========================
// LOAD TRANSACTIONS
// =========================

async function loadTransactions() {
    const container = document.getElementById("transactions");

    container.innerHTML = "Loading transactions...";

    try {
        const response = await fetch(
            `${API_URL}/transactions/${userId}`,
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            container.textContent =
                data.detail || "Unable to load transactions.";
            return;
        }

        if (data.length === 0) {
            container.textContent = "No transactions yet.";
            return;
        }

        container.innerHTML = "";

        data.forEach(transaction => {

            const div = document.createElement("div");

            div.className = "transaction";

            const amount =
                (transaction.amount_paise / 100).toFixed(2);

            div.innerHTML = `
                <strong>Transaction #${transaction.id}</strong>
                <br>
                From: User ${transaction.sender_id}
                <br>
                To: User ${transaction.receiver_id}
                <br>
                Amount: ₹${amount}
                <br>
                Status: ${transaction.status}
            `;

            container.appendChild(div);
        });

    } catch (error) {
        console.error(error);
        container.textContent =
            "Cannot connect to backend.";
    }
}


// =========================
// LOGOUT
// =========================

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("userId");
    localStorage.removeItem("userName");

    token = null;
    userId = null;
    userName = null;

    document.getElementById("dashboard-section")
        .classList.add("hidden");

    document.getElementById("login-section")
        .classList.remove("hidden");

    document.getElementById("email").value = "";
    document.getElementById("password").value = "";
}