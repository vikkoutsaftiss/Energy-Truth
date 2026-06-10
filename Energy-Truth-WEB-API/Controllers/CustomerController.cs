using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Energy_Truth_WEB_API.Services.Customer;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class CustomerController : ControllerBase
    {
        private readonly ICustomerService _customerService;

        public CustomerController(ICustomerService customerService)
        {
            _customerService = customerService;
        }

        [HttpPost("createcustomer")]
        public async Task<IActionResult> CreateCustomer([FromBody] CreateCustomerDTO customerDTO)
        {
            if (customerDTO == null)
            {
                return BadRequest("Ongeldige klantgegevens.");
            }

            if (string.IsNullOrEmpty(customerDTO.Email))
            {
                return BadRequest("E-mailadres is verplicht.");
            }

            if (string.IsNullOrEmpty(customerDTO.Password))
            {
                return BadRequest("Wachtwoord is verplicht.");
            }

            if (string.IsNullOrEmpty(customerDTO.Address))
            {
                return BadRequest("Adres is verplicht.");
            }

            try
            {
                var customerId = await _customerService.CreateCustomerAsync(customerDTO);

                
                if (customerId == 0)
                {
                    return BadRequest("Klant met dit e-mailadres bestaat al.");
                }
                return Ok(customerId);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Er is een fout opgetreden bij het aanmaken van de klant: {ex.Message}");
            }
        }
    }
}
