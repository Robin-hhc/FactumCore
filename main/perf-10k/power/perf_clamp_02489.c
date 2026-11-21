/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02489(unsigned int count)
{
    const unsigned int limit = 240u;
    return count > limit ? limit : count;
}
