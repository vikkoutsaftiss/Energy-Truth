using Microsoft.Playwright;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.E2ETests.PageObjects
{
    public class CsvImporterPage
    {
        private readonly IPage _page;

        public CsvImporterPage(IPage page)
        {
            _page = page;
        }

        public async Task GoToLoginPage()
        {
            await _page.GotoAsync("https://localhost:7140/login");
            await _page.WaitForSelectorAsync("#username", new()
            {
                State = WaitForSelectorState.Visible,
            });
        }

        public async Task GoToPageAsync()
        {
            await _page.GotoAsync("https://localhost:7140/csvimporter");
            await _page.WaitForSelectorAsync(".mud-select", new()
            {
                State = WaitForSelectorState.Visible,
            });
        }

        public async Task SelectProviderAsync(string providerName)
        {
            await _page.GetByTestId("provider-select").ClickAsync();
            await _page.GetByText(providerName).First.ClickAsync();
        }

        public async Task UploadFileAsync(string filePath)
        {
            await _page.WaitForSelectorAsync("input[type='file']", new()
            {
                State = WaitForSelectorState.Attached,
                Timeout = 10000
            });
            await _page.Locator("input[type='file']").SetInputFilesAsync(filePath);
        }

        public async Task ProcessDataAsync()
        {
            await _page.GetByTestId("process-data").ClickAsync();
        }

        public async Task StartCalculationAsync()
        {
            await _page.GetByTestId("start-calculation").ClickAsync();
        }

        public async Task<bool> IsCalculationResultVisibleAsync()
        {
            await _page.GetByTestId("total-import").WaitForAsync();
            return true;
        }
    }
}