import { test, expect } from '@playwright/test';

test.describe('Dashboard Tenant Isolation', () => {
    test('Dashboard loads properly without crashing', async ({ page }) => {
        // Navigating directly to dashboard
        await page.goto('/ariia/');

        // It should either redirect to login if unauthenticated or show the dashboard nav
        const loginInput = page.getByPlaceholder(/E-Mail/i);
        const navMenu = page.locator('nav');

        await expect(loginInput.or(navMenu).first()).toBeVisible({ timeout: 10000 });
    });
});
