using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;

namespace Energy_Truth_Presentation.Services
{
    public interface IAuthenticateService
    {
        LoggedInUser CurrentUser { get; }
        CustomBatteryDTO CustomBattery { get; set; }
        bool LogIn(LoggedInUser user);

        void LogOut();
    }
}
