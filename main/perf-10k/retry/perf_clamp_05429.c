/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05429(unsigned int count)
{
    const unsigned int limit = 171u;
    return count > limit ? limit : count;
}
