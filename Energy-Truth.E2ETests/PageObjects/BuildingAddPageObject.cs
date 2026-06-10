using Microsoft.Playwright;

namespace Energy_Truth.E2ETests.PageObjects
{
    public class BuildingAddPageObject(IPage page)
    {
        private readonly IPage _page = page;

        public async Task GoToBuildingPageAsync()
        {
            await _page.WaitForURLAsync("**/buildinglist**");
            await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
            await _page.GetByTestId("add-building-button").ClickAsync();
            await _page.WaitForSelectorAsync("[data-testid='postalcode-field']", new()
            {
                State = WaitForSelectorState.Visible
            });
        }

        public async Task FillPostalCodeAsync(string postalCode)
        {
            await _page.Locator("[data-testid='postalcode-field'] input").FillAsync(postalCode);
        }

        public async Task FillConstructionYearAsync(string year)
        {
            await _page.Locator("[data-testid='buildyear-field'] input").FillAsync(year);
        }

        public async Task SelectEnergyLabelAsync(string label)
        {
            await _page.GetByTestId("energylabel-select").ClickAsync();
            await _page.GetByText(label).First.ClickAsync();
        }

        public async Task SubmitAsync()
        {
            await _page.GetByTestId("submit-button").ClickAsync();
            await _page.WaitForURLAsync("**/buildinglist**");
        }


    }
}
