/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04199(unsigned int count)
{
    const unsigned int limit = 177u;
    return count > limit ? limit : count;
}
