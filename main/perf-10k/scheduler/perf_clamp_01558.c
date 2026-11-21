/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01558(unsigned int count)
{
    const unsigned int limit = 100u;
    return count > limit ? limit : count;
}
