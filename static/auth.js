async function handleSignup() {
    const data = {
        user_id: document.getElementById('join_id').value,
        user_pw: document.getElementById('join_pw').value,
        user_name: document.getElementById('join_name').value,
        role: document.getElementById('join_role').value,
        team_id: document.getElementById('join_team_id').value // 슬레이브용
    };

    const response = await fetch('/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    const result = await response.json();
    alert(result.message);
    if (response.ok) switchTab('login');
}

async function handleLogin() {
    const data = {
        user_id: document.getElementById('login_id').value,
        user_pw: document.getElementById('login_pw').value
    };

    const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    const result = await response.json();
    if (response.ok) {
        window.location.href = '/';
    } else {
        alert(result.message);
    }
}