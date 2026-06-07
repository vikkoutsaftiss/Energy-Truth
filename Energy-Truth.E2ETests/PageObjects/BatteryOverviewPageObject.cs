using Microsoft.Playwright;

namespace Energy_Truth.E2ETests.PageObjects
{
    public class BatteryOverviewPageObject(IPage page)
    {
        private readonly IPage _page = page;

        public async Task WaitForPageAsync()
        {
            await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
            // Wacht tot de "Doorgaan zonder custom batterij" knop zichtbaar is
            await _page.Locator("[data-testid='skip-battery-button']").WaitForAsync();
        }

        public async Task ContinueWithoutBatteryAsync()
        {
            await _page.Locator("[data-testid='skip-battery-button']").ClickAsync();
            await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        }
    }
}
