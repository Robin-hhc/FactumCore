/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08317(unsigned int count)
{
    const unsigned int limit = 214u;
    return count > limit ? limit : count;
}
