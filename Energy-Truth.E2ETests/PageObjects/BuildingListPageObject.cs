using Microsoft.Playwright;

namespace Energy_Truth.E2ETests.PageObjects
{
    public class BuildingListPageObject(IPage page)
    {
        private readonly IPage _page = page;

        public async Task GoToBuildingListAsync()
        {
            await _page.GotoAsync("/buildinglist");
            await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        }

        public async Task SelectFirstBuildingAsync()
        {
            var selectButton = _page.Locator("button:has-text('Selecteer')").First;
            await selectButton.WaitForAsync();
            await selectButton.ClickAsync();
            await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        }
    }
}
