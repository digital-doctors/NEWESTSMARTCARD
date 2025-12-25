document.addEventListener("DOMContentLoaded", () => {
    const addBtn = document.getElementById("add-gift-btn");
    const modal = document.getElementById("gift-modal");
    const closeBtns = document.querySelectorAll(".modal-close, .modal-cancel");
    const form = document.getElementById("gift-form");
    const list = document.getElementById("gift-cards-list");
    const emptyState = document.getElementById("empty-state");

    // ----------------------------
    // Modal logic
    // ----------------------------
    addBtn?.addEventListener("click", () => {
        modal.style.display = "flex";
    });

    closeBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            modal.style.display = "none";
        });
    });

    // ----------------------------
    // Load gift cards
    // ----------------------------
    async function loadGiftCards() {
        const res = await fetch("/get-gift-cards");
        if (!res.ok) return;

        const data = await res.json();
        list.innerHTML = "";

        if (!data.gift_cards || data.gift_cards.length === 0) {
            emptyState.style.display = "block";
            return;
        }

        emptyState.style.display = "none";

        data.gift_cards.forEach(card => {
            const el = document.createElement("div");
            el.className = "card";

            el.innerHTML = `
                <div class="card-header">
                    <h3>${card.brand}</h3>
                    <span class="card-balance">$${card.balance.toFixed(2)}</span>
                </div>
                ${card.notes ? `<p class="card-notes">${card.notes}</p>` : ""}
            `;

            list.appendChild(el);
        });
    }

    loadGiftCards();

    // ----------------------------
    // Add gift card
    // ----------------------------
    form?.addEventListener("submit", async (e) => {
        e.preventDefault();

        const brand = document.getElementById("gift-brand").value.trim();
        const balance = document.getElementById("gift-balance").value;
        const notes = document.getElementById("gift-notes").value.trim();

        if (!brand || balance === "") return;

        const res = await fetch("/add-gift-card", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ brand, balance, notes })
        });

        if (res.ok) {
            modal.style.display = "none";
            form.reset();
            loadGiftCards();
        } else {
            alert("Failed to add gift card");
        }
    });
});
