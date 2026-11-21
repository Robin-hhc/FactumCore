/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05558(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
