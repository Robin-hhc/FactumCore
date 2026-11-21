/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01867(unsigned int count)
{
    const unsigned int limit = 124u;
    return count > limit ? limit : count;
}
