import { test, expect } from '@playwright/test';

test.describe('Circuit Designer — User Experience', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('app loads with correct title and layout', async ({ page }) => {
    await expect(page).toHaveTitle('Circuit Designer');

    // Toolbar visible with circuit name
    const nameInput = page.locator('input[value="Untitled Circuit"]');
    await expect(nameInput).toBeVisible();

    // Component palette visible
    await expect(page.getByText('Components')).toBeVisible();

    // Stats in toolbar
    await expect(page.getByText('0 components')).toBeVisible();
    await expect(page.getByText('0 wires')).toBeVisible();
  });

  test('component palette shows categories', async ({ page }) => {
    await expect(page.getByText('Microcontrollers')).toBeVisible();
    // Expand sensors
    await page.getByText('Sensors').click();
    await expect(page.getByText('DHT11')).toBeVisible();
    await expect(page.getByText('HC-SR04')).toBeVisible();
  });

  test('search filters components', async ({ page }) => {
    const search = page.getByPlaceholder('Search components...');
    await search.fill('servo');
    await expect(page.getByText('Servo SG90')).toBeVisible();
    // Should not show unrelated items
    await expect(page.getByText('Arduino Uno')).not.toBeVisible();
  });

  test('clicking a component adds it to the canvas', async ({ page }) => {
    // Arduino Uno should be visible in the expanded Microcontrollers category
    await page.getByText('Arduino Uno').click();

    // Stats should update
    await expect(page.getByText('1 components')).toBeVisible();

    // The node should appear on canvas
    const node = page.locator('.react-flow__node');
    await expect(node).toHaveCount(1);
  });

  test('adding multiple components updates count', async ({ page }) => {
    await page.getByText('Arduino Uno').click();
    await page.getByText('ESP32 DevKit').click();

    await expect(page.getByText('2 components')).toBeVisible();
    const nodes = page.locator('.react-flow__node');
    await expect(nodes).toHaveCount(2);
  });

  test('selecting a component shows properties panel', async ({ page }) => {
    await page.getByText('Arduino Uno').click();

    // Click the node on canvas
    const node = page.locator('.react-flow__node').first();
    await node.click();

    // Properties panel should show the component name and details
    await expect(page.getByText('ATmega328P-based development board')).toBeVisible();
  });

  test('properties panel shows pin list', async ({ page }) => {
    // Add a DHT11
    await page.getByText('Sensors').click();
    await page.getByText('DHT11').click();

    // Select it
    const node = page.locator('.react-flow__node').first();
    await node.click();

    // Should see pins listed
    await expect(page.getByText('VCC')).toBeVisible();
    await expect(page.getByText('DATA')).toBeVisible();
    await expect(page.getByText('GND')).toBeVisible();
  });

  test('delete component from properties panel', async ({ page }) => {
    await page.getByText('Arduino Uno').click();
    await expect(page.getByText('1 components')).toBeVisible();

    // Select it
    const node = page.locator('.react-flow__node').first();
    await node.click();

    // Delete
    await page.getByText('Delete Component').click();
    await expect(page.getByText('0 components')).toBeVisible();
  });

  test('circuit validation reports issues', async ({ page }) => {
    // Add a lone LED
    await page.getByText('Passive Components').click();
    await page.getByText('LED').click();

    // Run validation
    await page.getByText('Run Check').click();

    // Should see warnings
    await expect(page.getByText(/not connected/)).toBeVisible();
    await expect(page.getByText(/microcontroller/i)).toBeVisible();
  });

  test('rename circuit via toolbar', async ({ page }) => {
    const nameInput = page.locator('input[value="Untitled Circuit"]');
    await nameInput.triple_click();
    await nameInput.fill('My Test Circuit');
    await expect(page.locator('input[value="My Test Circuit"]')).toBeVisible();
  });

  test('clear circuit removes all components', async ({ page }) => {
    await page.getByText('Arduino Uno').click();
    await page.getByText('ESP32 DevKit').click();
    await expect(page.getByText('2 components')).toBeVisible();

    await page.getByText('Clear').click();
    await expect(page.getByText('0 components')).toBeVisible();
  });

  test('export produces a downloadable JSON file', async ({ page }) => {
    await page.getByText('Arduino Uno').click();

    // Listen for download
    const downloadPromise = page.waitForEvent('download');
    await page.getByText('Export').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain('.circuit.json');
  });

  test('drag and drop from palette to canvas', async ({ page }) => {
    // Get the LED item in the palette
    await page.getByText('Passive Components').click();
    const ledButton = page.getByText('LED').first();

    // Get the canvas area
    const canvas = page.locator('.react-flow');

    // Perform drag-and-drop
    await ledButton.dragTo(canvas, { targetPosition: { x: 300, y: 200 } });

    // Verify a node appeared
    await expect(page.getByText('1 components')).toBeVisible();
  });

  test('canvas zoom controls are visible', async ({ page }) => {
    // React Flow controls panel should be present
    const controls = page.locator('.react-flow__controls');
    await expect(controls).toBeVisible();
  });

  test('minimap is visible', async ({ page }) => {
    const minimap = page.locator('.react-flow__minimap');
    await expect(minimap).toBeVisible();
  });

  test('component nodes show pin handles', async ({ page }) => {
    await page.getByText('Sensors').click();
    await page.getByText('DHT11').click();

    // Pin handles should be present
    const handles = page.locator('.react-flow__handle');
    // DHT11 has 3 pins
    await expect(handles).toHaveCount(3);
  });
});
