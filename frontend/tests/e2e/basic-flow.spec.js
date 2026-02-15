import { test, expect } from '@playwright/test';

test('basic schema creation and generation flow', async ({ page }) => {
    await page.addInitScript(() => {
        class MockWebSocket {
            constructor(url) {
                this.url = url;
                this.readyState = 0;
                setTimeout(() => {
                    this.readyState = 1;
                    if (this.onopen) this.onopen();

                    if (this.onmessage) {
                        this.onmessage({ data: JSON.stringify({ status: 'running', progress: 50 }) });
                        setTimeout(() => {
                            this.onmessage({ data: JSON.stringify({ status: 'completed', progress: 100 }) });
                        }, 500);
                    }
                }, 100);
            }
            close() { }
        }
        window.WebSocket = MockWebSocket;
    });

    await page.route('**/token', async route => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ access_token: 'fake-jwt-token' })
        });
    });

    await page.route('**/generate/async', async route => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ job_id: 'job-123' })
        });
    });

    await page.route('**/jobs/*/result', async route => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                status: 'completed',
                data: [
                    { id: 1, name: 'Test User', email: 'test@example.com' }
                ]
            })
        });
    });

    await page.goto('/');

    const loginButton = page.locator('button:has-text("Sign In")');
    if (await loginButton.isVisible()) {
        await page.fill('input[placeholder="Enter username"]', 'admin');
        await page.fill('input[placeholder="Enter password"]', 'admin');
        await loginButton.click();
    }

    await expect(page).toHaveTitle(/DataSynth/);

    await page.click('text=Add Table');

    const tableNameInput = page.locator('input[placeholder="Table Name"]').last();
    await tableNameInput.fill('users');

    await page.fill('input[placeholder="e.g. user_id"]', 'name');

    await page.click('button:has-text("Add Field")');

    await page.click('button:has-text("Run Generation")');

    await page.click('button:has-text("Download Result")');

    await expect(page.locator('text=Data generated!')).toBeVisible({ timeout: 20000 });
});
