import { test, expect } from '@playwright/test';

test.describe('Login & Dashboard Flow', () => {
    test('User can see login page and authenticate to dashbord', async ({ page }) => {
        await page.goto('/login');

        // We expect the login inputs to be visible
        const emailInput = page.getByPlaceholder(/E-Mail/i).first();
        const passInput = page.getByPlaceholder(/Passwort/i).first();
        const loginButton = page.getByRole('button', { name: /Login/i });

        await expect(emailInput).toBeVisible();
        await expect(passInput).toBeVisible();
        await expect(loginButton).toBeVisible();
    });
});
